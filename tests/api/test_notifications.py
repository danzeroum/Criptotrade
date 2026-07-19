"""A6 notifications: encrypted+masked channel secrets, real test-send wiring,
rule routing with retry/backoff, quiet hours (midnight-crossing, tz-aware),
anti-flood grouping, optimistic single-dispatcher cursor and the alerts-config
read-back."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.core.alerts import Alert, AlertStore
from src.core.db import get_db_path, init_db
from src.notifications import dispatcher as dispatcher_mod
from src.notifications.dispatcher import Dispatcher
from src.notifications.store import NotificationStore


@pytest.fixture
def notif_env(tmp_path, monkeypatch):
    """AUTH_MODE=off (legacy pass on require_perm) + fast retries."""
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key-notifications")  # gitleaks:allow (test fixture)
    monkeypatch.delenv("AUTH_MODE", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.setattr(dispatcher_mod, "BACKOFF_S", [0.0, 0.0])
    deps.reset_singletons()
    init_db()
    yield NotificationStore()
    deps.reset_singletons()


def _client() -> TestClient:
    return TestClient(create_app())


class _FakeSender:
    """Capture deliveries; optionally fail the first N calls per channel kind."""

    def __init__(self, fail_times: int = 0):
        self.sent = []
        self.fail_times = fail_times
        self.calls = 0

    def __call__(self, kind, config, subject, text, payload=None):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("entrega recusada (fake)")
        self.sent.append({"kind": kind, "config": config,
                          "subject": subject, "text": text})


def _write_alert(severity="critical", a_type="circuit_breaker",
                 message="Circuit breaker TRIPPED", pair=None) -> Alert:
    alert = Alert(severity=severity, type=a_type, message=message, pair=pair)
    AlertStore().append(alert)
    return alert


# --------------------------------------------------- aceite 1: canal + secrets
def test_channel_secret_is_encrypted_masked_and_patch_idempotent(notif_env):
    client = _client()
    r = client.post("/v1/notifications/channels", json={
        "kind": "telegram", "label": "Ops",
        "config": {"bot_token": "123456:AAAbbbCCCddd-secret-4821", "chat_id": "-100200"},
    })
    assert r.status_code == 201, r.text
    out = r.json()["data"]
    assert out["config_masked"]["bot_token"] == "•••4821"
    assert out["destination_masked"] == "chat -100200 · token •••4821"

    # At rest: the stored row never contains the plaintext token.
    with sqlite3.connect(get_db_path()) as conn:
        (config_enc,) = conn.execute(
            "SELECT config_enc FROM notification_channels WHERE id = ?", (out["id"],)
        ).fetchone()
    assert "secret-4821" not in config_enc

    # GET stays masked; PATCH echoing the mask keeps the stored secret.
    listed = client.get("/v1/notifications/channels").json()["data"][0]
    assert listed["config_masked"]["bot_token"] == "•••4821"
    r2 = client.patch(f"/v1/notifications/channels/{out['id']}", json={
        "label": "Ops-2",
        "config": {"bot_token": "•••4821", "chat_id": "-100200"},
    })
    assert r2.status_code == 200
    stored = notif_env.channel_config(notif_env.get_channel(out["id"]))
    assert stored["bot_token"] == "123456:AAAbbbCCCddd-secret-4821"

    # Incomplete config on create → 422.
    assert client.post("/v1/notifications/channels", json={
        "kind": "telegram", "label": "X", "config": {"chat_id": "1"},
    }).status_code == 422


def test_test_send_hits_telegram_and_records_status(notif_env, monkeypatch):
    client = _client()
    ch = client.post("/v1/notifications/channels", json={
        "kind": "telegram", "label": "Ops",
        "config": {"bot_token": "tok-999", "chat_id": "42"},
    }).json()["data"]

    calls = {}

    class _Resp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):  # noqa: A003 - mimics httpx.Response
            return {"ok": True}

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls["json"] = kwargs.get("json")
        return _Resp()

    monkeypatch.setattr("src.notifications.senders.httpx.post", fake_post)
    r = client.post(f"/v1/notifications/channels/{ch['id']}/test")
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["ok"] is True
    assert body["destination"].startswith("chat 42")
    assert calls["url"] == "https://api.telegram.org/bottok-999/sendMessage"
    assert calls["json"]["chat_id"] == "42"
    row = notif_env.get_channel(ch["id"])
    assert row["last_test_ok"] == 1

    # A failing channel reports the reason and records the error.
    def bad_post(url, **kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr("src.notifications.senders.httpx.post", bad_post)
    body = client.post(f"/v1/notifications/channels/{ch['id']}/test").json()["data"]
    assert body["ok"] is False and "connection refused" in body["error"]
    assert notif_env.get_channel(ch["id"])["last_test_ok"] == 0


# ------------------------------------------- aceite 2: regra crítica → canais
def test_critical_rule_delivers_to_chosen_channels(notif_env, monkeypatch):
    store = notif_env
    ch1 = store.create_channel("telegram", "TG", {"bot_token": "t", "chat_id": "1"})
    ch2 = store.create_channel("email", "Mail", {"to_email": "dono@x.dev"})
    store.create_channel("slack", "Slack", {"webhook_url": "https://hooks.slack/x"})  # not in the rule
    store.create_rule("circuit_breaker", "critical", [ch1["id"], ch2["id"]])

    fake = _FakeSender()
    monkeypatch.setattr("src.notifications.dispatcher.send_via_channel", fake)
    _write_alert(severity="critical", a_type="circuit_breaker")

    d = Dispatcher(store=store, ledger=deps.get_ledger())
    assert d.dispatch_pending() == 1
    kinds = sorted(s["kind"] for s in fake.sent)
    assert kinds == ["email", "telegram"]  # ch3 (slack) was NOT in the rule
    events = deps.get_ledger().get_events("notification_sent")
    assert len(events) == 2
    assert all(e["data"]["actor"] == "notifier" for e in events)
    assert {e["data"]["channel_kind"] for e in events} == {"email", "telegram"}

    # A low alert does not match the critical rule.
    _write_alert(severity="low", a_type="circuit_breaker")
    assert d.dispatch_pending() == 1
    assert len(fake.sent) == 2  # unchanged


def test_delivery_failure_retries_then_logs_failed(notif_env, monkeypatch):
    store = notif_env
    ch = store.create_channel("slack", "Slack", {"webhook_url": "https://h/x"})
    store.create_rule("*", "high", [ch["id"]])
    fake = _FakeSender(fail_times=99)  # always fails → 3 attempts then give up
    monkeypatch.setattr("src.notifications.dispatcher.send_via_channel", fake)
    _write_alert(severity="high", a_type="guardrail_violation")

    d = Dispatcher(store=store, ledger=deps.get_ledger())
    d.dispatch_pending()
    assert fake.calls == 3  # 1 + 2 retries (BACKOFF_S shrunk by the fixture)
    failed = deps.get_ledger().get_events("notification_failed")
    assert len(failed) == 1
    assert failed[0]["data"]["attempts"] == 3
    assert deps.get_ledger().get_events("notification_sent") == []


# --------------------------------------------------- aceite 3: quiet hours
def test_quiet_hours_suppress_low_but_not_critical(notif_env, monkeypatch):
    store = notif_env
    ch = store.create_channel("telegram", "TG", {"bot_token": "t", "chat_id": "1"})
    store.create_rule("*", "low", [ch["id"]])
    # 22:00–07:00 crossing midnight, in São Paulo (UTC-3).
    store.set_settings(quiet_start="22:00", quiet_end="07:00",
                       quiet_tz="America/Sao_Paulo")
    fake = _FakeSender()
    monkeypatch.setattr("src.notifications.dispatcher.send_via_channel", fake)
    d = Dispatcher(store=store, ledger=deps.get_ledger())

    # 02:30 UTC = 23:30 in São Paulo → inside the window.
    inside = datetime(2026, 7, 18, 2, 30, tzinfo=timezone.utc)
    _write_alert(severity="low", a_type="behavioral")
    assert d.dispatch_pending(now=inside) == 1
    assert fake.sent == []  # suppressed: external delivery only
    assert deps.get_ledger().get_events("notification_sent") == []

    _write_alert(severity="critical", a_type="circuit_breaker")
    assert d.dispatch_pending(now=inside) == 1
    assert len(fake.sent) == 1  # critical always passes

    # 15:00 UTC = 12:00 in São Paulo → outside the window: low delivers.
    outside = datetime(2026, 7, 18, 15, 0, tzinfo=timezone.utc)
    _write_alert(severity="low", a_type="behavioral")
    assert d.dispatch_pending(now=outside) == 1
    assert len(fake.sent) == 2


def test_grouping_suppresses_repeats_and_annotates(notif_env, monkeypatch):
    store = notif_env
    ch = store.create_channel("slack", "S", {"webhook_url": "https://h/x"})
    store.create_rule("*", "low", [ch["id"]])
    store.set_settings(group_window_min=5)
    fake = _FakeSender()
    monkeypatch.setattr("src.notifications.dispatcher.send_via_channel", fake)
    d = Dispatcher(store=store, ledger=deps.get_ledger())

    t0 = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
    for _ in range(4):
        _write_alert(severity="high", a_type="guardrail_violation", pair="BTC/USDT")
    d.dispatch_pending(now=t0)
    assert len(fake.sent) == 1  # first delivers, 3 suppressed in the window

    t1 = datetime(2026, 7, 18, 12, 6, tzinfo=timezone.utc)  # window elapsed
    _write_alert(severity="high", a_type="guardrail_violation", pair="BTC/USDT")
    d.dispatch_pending(now=t1)
    assert len(fake.sent) == 2
    assert "(+3 suprimidos" in fake.sent[1]["text"]


# ------------------------------------------------ dispatcher único / cursor
def test_cursor_is_claimed_optimistically_and_never_redelivers(notif_env, monkeypatch):
    store = notif_env
    ch = store.create_channel("slack", "S", {"webhook_url": "https://h/x"})
    store.create_rule("*", "low", [ch["id"]])
    fake = _FakeSender()
    monkeypatch.setattr("src.notifications.dispatcher.send_via_channel", fake)
    d = Dispatcher(store=store, ledger=deps.get_ledger())

    _write_alert(severity="high")
    assert d.dispatch_pending() == 1
    assert d.dispatch_pending() == 0  # nothing new
    # A competing worker that lost the race sees rowcount 0 and skips.
    assert store.advance_cursor(0, 999) is False
    # Fresh dispatcher instance (API restart) does not re-deliver.
    d2 = Dispatcher(store=store, ledger=deps.get_ledger())
    assert d2.dispatch_pending() == 0
    assert len(fake.sent) == 1


def test_first_boot_skips_history(notif_env):
    _write_alert(severity="critical")
    d = Dispatcher(store=notif_env, ledger=deps.get_ledger())
    d.ensure_initialized()  # no cursor yet → start at EOF, not at zero
    assert d.dispatch_pending() == 0


# ----------------------------------------------------- read-back + RBAC
def test_alerts_config_readback_mirrors_patch(notif_env):
    client = _client()
    before = client.get("/v1/alerts/config").json()["data"]
    assert "revenge_size_multiplier" in before
    from src.api.routes import config as config_route

    saved = dict(config_route._behavioral_thresholds)
    try:
        client.patch("/v1/alerts/config", json={"risk_of_ruin_alert_pct": 7.5})
        after = client.get("/v1/alerts/config").json()["data"]
        assert after["risk_of_ruin_alert_pct"] == 7.5
    finally:
        config_route._behavioral_thresholds.clear()
        config_route._behavioral_thresholds.update(saved)


def test_notifications_require_edit_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_MODE", "required")
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key-notifications")  # gitleaks:allow (test fixture)
    monkeypatch.delenv("API_KEYS", raising=False)
    deps.reset_singletons()
    init_db()
    from src.api.routes.auth import reset_login_limiter

    reset_login_limiter()
    from src.auth.store import UserStore

    users = UserStore()
    users.create("op@x.dev", "password-op", role="operador")  # gitleaks:allow (test fixture)
    users.create("root@x.dev", "password-root", role="admin")  # gitleaks:allow (test fixture)

    def login(email, pwd):
        c = TestClient(create_app())
        assert c.post("/v1/auth/login", json={"email": email, "password": pwd}).status_code == 200
        return c

    operator = login("op@x.dev", "password-op")
    r = operator.get("/v1/notifications/channels")
    assert r.status_code == 403
    assert r.json()["required_permission"] == "edit_settings"

    admin = login("root@x.dev", "password-root")
    assert admin.get("/v1/notifications/channels").status_code == 200
    deps.reset_singletons()


# ------------------------------------------------- N7: pair scope on rules
def test_rule_pair_scope_matches_only_that_pair(notif_env, monkeypatch):
    store = notif_env
    ch = store.create_channel("telegram", "TG", {"bot_token": "t", "chat_id": "1"})
    store.create_rule("*", "critical", [ch["id"]], pairs=["BTC/USDT"])  # BTC-only rule
    fake = _FakeSender()
    monkeypatch.setattr("src.notifications.dispatcher.send_via_channel", fake)
    d = Dispatcher(store=store, ledger=deps.get_ledger())

    _write_alert(severity="critical", a_type="signal", pair="XRP/USDT")
    d.dispatch_pending()
    assert fake.sent == []  # XRP alert does not match a BTC-only rule

    _write_alert(severity="critical", a_type="signal", pair="BTC/USDT")
    d.dispatch_pending()
    assert len(fake.sent) == 1  # BTC alert matches


def test_system_alert_without_pair_matches_a_scoped_rule(notif_env, monkeypatch):
    """The load-bearing semantic: a global breaker (pair=None) must NOT be
    silenced by a pair-scoped rule."""
    store = notif_env
    ch = store.create_channel("telegram", "TG", {"bot_token": "t", "chat_id": "1"})
    store.create_rule("circuit_breaker", "critical", [ch["id"]], pairs=["BTC/USDT"])
    fake = _FakeSender()
    monkeypatch.setattr("src.notifications.dispatcher.send_via_channel", fake)
    d = Dispatcher(store=store, ledger=deps.get_ledger())

    _write_alert(severity="critical", a_type="circuit_breaker", pair=None)
    d.dispatch_pending()
    assert len(fake.sent) == 1  # system alert reaches the BTC-scoped rule


def test_legacy_rule_defaults_to_all_pairs(notif_env, monkeypatch):
    store = notif_env
    ch = store.create_channel("telegram", "TG", {"bot_token": "t", "chat_id": "1"})
    rule = store.create_rule("*", "critical", [ch["id"]])  # no pairs → ["*"]
    assert rule["pairs"] == ["*"]
    fake = _FakeSender()
    monkeypatch.setattr("src.notifications.dispatcher.send_via_channel", fake)
    d = Dispatcher(store=store, ledger=deps.get_ledger())

    _write_alert(severity="critical", a_type="signal", pair="XRP/USDT")
    d.dispatch_pending()
    assert len(fake.sent) == 1  # a default rule still fires for every pair


def test_patch_rule_pairs_via_api(notif_env):
    store = notif_env
    ch = store.create_channel("telegram", "TG", {"bot_token": "t", "chat_id": "1"})
    rule = store.create_rule("*", "high", [ch["id"]])
    client = _client()
    r = client.patch(f"/v1/notifications/rules/{rule['id']}", json={"pairs": ["BTC/USDT", "ETH/USDT"]})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["pairs"] == ["BTC/USDT", "ETH/USDT"]
    assert store.get_rule(rule["id"])["pairs"] == ["BTC/USDT", "ETH/USDT"]
