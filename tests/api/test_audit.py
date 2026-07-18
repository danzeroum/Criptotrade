"""A4 audit trail: normalization, SQL-side filters (pagination correctness
under the actor filter), detail/diff, complete hardened export, RBAC gates and
the new config_changed emission."""
from __future__ import annotations

import csv
import io
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.core.db import init_db


def _seed_basic(led) -> None:
    led.log_auth_event("login", actor="ana@x.dev", email="ana@x.dev",
                       ip="10.0.0.1", user_agent="pytest-ua", success=True)
    led.log_hitl_approval(True, {"id": "o-1", "pair": "BTC/USDT"}, user="op@x.dev")
    led.log_hitl_approval(False, {"id": "o-2", "pair": "ETH/USDT"}, user="op@x.dev")
    led.log_decision("hitl_level_changed", {
        "level": 2, "previous_level": 1, "reason": "teste de trilha", "operator": "root@x.dev",
    })
    led.log_decision("config_changed", {
        "actor": "root@x.dev", "scope": "risk",
        "before": {"max_daily_loss_pct": 5.0}, "after": {"max_daily_loss_pct": 4.0},
    })
    led.log_position_closed("o-1", "BTC/USDT", "buy", 100.0, 110.0, 1.0)
    led.log_decision("circuit_breaker_tripped", {"reason": "3 perdas consecutivas"})
    led.log_execution("execution", {"symbol": "BTC/USDT", "status": "ok"})
    # High-frequency telemetry — must NOT surface in the trail.
    led.log_fill("o-9", "BTC/USDT", "buy", 100.0, 1.0)
    led.log_signal("technical", {"action": "buy"})


@pytest.fixture
def audit_env(tmp_path, monkeypatch):
    """AUTH_MODE=off + no API keys: routes open (legacy), focus on the trail."""
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.delenv("AUTH_MODE", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)
    deps.reset_singletons()
    init_db()
    yield deps.get_ledger()
    deps.reset_singletons()


def _client() -> TestClient:
    return TestClient(create_app())


# ------------------------------------------------------------ acceptance 1: map
def test_list_normalizes_and_excludes_telemetry(audit_env):
    _seed_basic(audit_env)
    r = _client().get("/v1/audit")
    assert r.status_code == 200, r.text
    body = r.json()
    # order_fill and signal_generated are out: 8 auditable events seeded.
    assert body["meta"]["total"] == 8
    by_action = {e["action"]: e for e in body["data"]}
    assert set(by_action) == {
        "login", "order_approved", "order_rejected", "autonomy_changed",
        "config_changed", "position_closed", "circuit_breaker", "order_executed",
    }
    login = by_action["login"]
    assert (login["actor"], login["ip"], login["ua"], login["success"]) == \
        ("ana@x.dev", "10.0.0.1", "pytest-ua", True)
    # System events are attributed, never blank (nota 2 da revisão).
    assert by_action["position_closed"]["actor"] == "orchestrator"
    assert by_action["circuit_breaker"]["actor"] == "orchestrator"
    assert by_action["order_executed"]["actor"] == "execution"
    # Newest first.
    ids = [e["id"] for e in body["data"]]
    assert ids == sorted(ids, reverse=True)


def test_autonomy_diff_carries_previous_level(audit_env):
    _seed_basic(audit_env)
    r = _client().get("/v1/audit?action=autonomy_changed")
    (event,) = r.json()["data"]
    assert event["before"] == {"level": 1}
    assert event["after"] == {"level": 2}
    assert event["detail"] == "teste de trilha"


# --------------------------------- acceptance 2: actor filter never breaks pages
def test_actor_filter_pagination_full_pages_and_exact_total(audit_env):
    # Interleave two actors so a post-SQL filter would produce ragged pages.
    for i in range(25):
        audit_env.log_auth_event("login", actor="alice@x.dev", email="alice@x.dev")
        audit_env.log_auth_event("login", actor="bob@x.dev", email="bob@x.dev")
    client = _client()

    page1 = client.get("/v1/audit?actor=alice@x.dev&limit=10&offset=0").json()
    assert page1["meta"]["total"] == 25
    assert len(page1["data"]) == 10
    assert all(e["actor"] == "alice@x.dev" for e in page1["data"])

    page3 = client.get("/v1/audit?actor=alice@x.dev&limit=10&offset=20").json()
    assert page3["meta"]["total"] == 25
    assert len(page3["data"]) == 5
    assert all(e["actor"] == "alice@x.dev" for e in page3["data"])


def test_action_and_entity_filters(audit_env):
    _seed_basic(audit_env)
    client = _client()
    approved = client.get("/v1/audit?action=order_approved").json()
    assert [e["entity"] for e in approved["data"]] == ["BTC/USDT"]
    rejected = client.get("/v1/audit?action=order_rejected").json()
    assert [e["entity"] for e in rejected["data"]] == ["ETH/USDT"]
    # Entity is a case-insensitive substring match, same predicate in export.
    eth = client.get("/v1/audit?entity=eth").json()
    assert eth["meta"]["total"] == 1 and eth["data"][0]["entity"] == "ETH/USDT"
    risk = client.get("/v1/audit?entity=risk").json()
    assert [e["action"] for e in risk["data"]] == ["config_changed"]
    assert client.get("/v1/audit?action=nope").status_code == 422


def test_time_filters_bare_dates_are_inclusive(audit_env):
    led = audit_env
    led.log_decision("config_changed", {"actor": "a@x.dev", "scope": "risk",
                                        "before": {}, "after": {}},
                     timestamp="2026-01-01T08:00:00+00:00")
    led.log_decision("config_changed", {"actor": "a@x.dev", "scope": "risk",
                                        "before": {}, "after": {}},
                     timestamp="2026-01-02T23:59:00+00:00")
    led.log_decision("config_changed", {"actor": "a@x.dev", "scope": "risk",
                                        "before": {}, "after": {}},
                     timestamp="2026-01-03T00:10:00+00:00")
    client = _client()
    assert client.get("/v1/audit?from=2026-01-02").json()["meta"]["total"] == 2
    assert client.get("/v1/audit?to=2026-01-02").json()["meta"]["total"] == 2
    assert client.get(
        "/v1/audit?from=2026-01-02&to=2026-01-02").json()["meta"]["total"] == 1
    assert client.get("/v1/audit?from=not-a-date").status_code == 422


# ----------------------------------------------------------------- detail (diff)
def test_detail_returns_raw_payload_and_404s(audit_env):
    _seed_basic(audit_env)
    client = _client()
    cfg = client.get("/v1/audit?action=config_changed").json()["data"][0]
    detail = client.get(f"/v1/audit/{cfg['id']}").json()["data"]
    assert detail["event_type"] == "config_changed"
    assert detail["before"] == {"max_daily_loss_pct": 5.0}
    assert detail["after"] == {"max_daily_loss_pct": 4.0}
    assert detail["data"]["scope"] == "risk"

    assert client.get("/v1/audit/999999").status_code == 404
    # A real ledger id that is NOT auditable (an order_fill) is also a 404.
    with sqlite3.connect(audit_env.db_path) as conn:
        fill_id = conn.execute(
            "SELECT id FROM ledger_events WHERE event_type='order_fill'"
        ).fetchone()[0]
    r = client.get(f"/v1/audit/{fill_id}")
    assert r.status_code == 404
    assert r.json()["error"] == "audit_event_not_found"


# ---------------------------------------------------------------------- export
def test_export_streams_the_complete_filtered_set(audit_env):
    for _ in range(25):
        audit_env.log_auth_event("login", actor="alice@x.dev", email="alice@x.dev")
        audit_env.log_auth_event("login", actor="bob@x.dev", email="bob@x.dev")
    client = _client()
    r = client.get("/v1/audit/export?format=csv&actor=alice@x.dev")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0][:4] == ["id", "ts", "action", "actor"]
    body = rows[1:]
    assert len(body) == 25  # the full filtered set, not one page
    assert all(row[3] == "alice@x.dev" for row in body)

    j = client.get("/v1/audit/export?format=json&actor=bob@x.dev")
    parsed = json.loads(j.text)
    assert len(parsed) == 25
    assert all(e["actor"] == "bob@x.dev" for e in parsed)


def test_export_csv_neutralizes_formula_injection(audit_env):
    audit_env.log_auth_event("login", actor="=2+5", email="+SUM(A1:A9)@x.dev",
                             detail="@cmd|' /C calc'!A0")
    r = _client().get("/v1/audit/export?format=csv")
    rows = list(csv.reader(io.StringIO(r.text)))
    header, (row,) = rows[0], rows[1:]
    cells = dict(zip(header, row))
    # Cells starting with = + - @ are prefixed so spreadsheets keep them as text.
    assert cells["actor"] == "'=2+5"
    assert cells["entity"] == "'+SUM(A1:A9)@x.dev"
    assert cells["detail"] == "'@cmd|' /C calc'!A0"


# ------------------------------------------------------------------ RBAC gates
@pytest.fixture
def rbac_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_MODE", "required")
    monkeypatch.setenv("API_KEYS", "machine-key")
    monkeypatch.delenv("AUTH_SECRET_KEY", raising=False)
    deps.reset_singletons()
    init_db()
    from src.api.routes.auth import reset_login_limiter

    reset_login_limiter()
    from src.auth.store import UserStore

    users = UserStore()
    users.create("viewer@x.dev", "password-viewer", role="visualizador")  # gitleaks:allow (test fixture)
    users.create("op@x.dev", "password-op", role="operador")  # gitleaks:allow (test fixture)
    yield users
    deps.reset_singletons()


def _login(client: TestClient, email: str, password: str) -> None:
    r = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text


def test_view_audit_gates_list_and_export(rbac_env):
    viewer = TestClient(create_app())
    _login(viewer, "viewer@x.dev", "password-viewer")
    r = viewer.get("/v1/audit")
    assert r.status_code == 403
    assert r.json()["required_permission"] == "view_audit"
    assert viewer.get("/v1/audit/export?format=csv").status_code == 403

    operator = TestClient(create_app())
    _login(operator, "op@x.dev", "password-op")
    assert operator.get("/v1/audit").status_code == 200

    machine = TestClient(create_app())
    assert machine.get("/v1/audit", headers={"X-API-Key": "machine-key"}).status_code == 200


def test_demo_principal_has_no_audit_access(tmp_path, monkeypatch):
    """Decisão de demo: a trilha contém e-mail/IP reais — o demo nunca a vê."""
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_MODE", "demo")
    monkeypatch.delenv("API_KEYS", raising=False)
    deps.reset_singletons()
    init_db()
    client = TestClient(create_app())
    for path in ("/v1/audit", "/v1/audit/export?format=csv", "/v1/audit/1"):
        r = client.get(path)
        assert r.status_code == 403, path
        assert r.json()["required_permission"] == "view_audit"
    deps.reset_singletons()


# -------------------------------------------------- config_changed emission
def test_config_patch_emits_before_after_event(audit_env):
    from src.api.routes import config as config_route

    saved = dict(config_route._runtime_overrides)
    try:
        client = _client()
        r = client.patch("/v1/config", json={"initial_capital": 12345.0})
        assert r.status_code == 200, r.text
        events = audit_env.get_events("config_changed")
        assert events, "PATCH /v1/config must log config_changed"
        data = events[-1]["data"]
        assert data["scope"] == "system"
        assert data["after"] == {"initial_capital": 12345.0}
        assert "initial_capital" in data["before"]
        assert data["actor"] == "anonymous"  # legacy AUTH_MODE=off caller

        # A no-op patch (same value) adds nothing.
        n = len(audit_env.get_events("config_changed"))
        client.patch("/v1/config", json={"initial_capital": 12345.0})
        assert len(audit_env.get_events("config_changed")) == n
    finally:
        config_route._runtime_overrides.clear()
        config_route._runtime_overrides.update(saved)


def test_risk_patch_emits_changed_keys_only(audit_env, tmp_path, monkeypatch):
    import yaml

    from src.api.routes import risk as risk_route

    params = tmp_path / "risk_params.yaml"
    params.write_text(yaml.dump({"loss_limits": {"max_daily_loss_pct": 5.0}}))
    monkeypatch.setattr(risk_route, "_RISK_PARAMS_PATH", params)
    r = _client().patch("/v1/risk/config",
                        json={"confirm": True, "max_daily_loss_pct": 3.5})
    assert r.status_code == 200, r.text
    data = audit_env.get_events("config_changed")[-1]["data"]
    assert data["scope"] == "risk"
    assert data["before"] == {"max_daily_loss_pct": 5.0}
    assert data["after"] == {"max_daily_loss_pct": 3.5}


def test_alerts_patch_emits_event(audit_env):
    from src.api.routes import config as config_route

    saved = dict(config_route._behavioral_thresholds)
    try:
        r = _client().patch("/v1/alerts/config", json={"revenge_size_multiplier": 1.8})
        assert r.status_code == 200, r.text
        data = audit_env.get_events("config_changed")[-1]["data"]
        assert data["scope"] == "alerts"
        assert data["before"] == {"revenge_size_multiplier": 1.5}
        assert data["after"] == {"revenge_size_multiplier": 1.8}
    finally:
        config_route._behavioral_thresholds.clear()
        config_route._behavioral_thresholds.update(saved)
