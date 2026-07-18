"""A10 onboarding: honest auto-detection (signals derived on every GET),
human-only persistence, the one-time completion stamp that survives restarts,
the brownfield first-GET (a running VPS never sees the wizard on upgrade) and
the admin-user-only gate."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.auth.store import UserStore
from src.core.db import init_db
from src.exchanges.store import ConnectionStore
from src.onboarding.status import OnboardingStore, compute_status


@pytest.fixture
def onb_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key-onboarding")  # gitleaks:allow (test fixture)
    monkeypatch.setenv("AUTH_MODE", "required")
    monkeypatch.delenv("API_KEYS", raising=False)
    deps.reset_singletons()
    init_db()
    from src.api.routes.auth import reset_login_limiter

    reset_login_limiter()
    users = UserStore()
    users.create("root@x.dev", "password-root", role="admin")  # gitleaks:allow (test fixture)
    users.create("op@x.dev", "password-op", role="operador")  # gitleaks:allow (test fixture)
    yield deps.get_ledger()
    deps.reset_singletons()


def _admin() -> TestClient:
    client = TestClient(create_app())
    r = client.post("/v1/auth/login", json={"email": "root@x.dev",
                                            "password": "password-root"})
    assert r.status_code == 200, r.text
    return client


def _steps(body) -> dict:
    return {s["id"]: s["status"] for s in body["data"]["steps"]}


def _seed_connection(tested: bool = True) -> str:
    store = ConnectionStore()
    row = store.create("binance", "principal", "key-abc123", "secret-abc123",
                       scope="read", testnet=True)
    store.activate(row["id"])
    if tested:
        store.record_test(row["id"], True, {"read_ok": True})
    return row["id"]


# ------------------------------------------------------- detection matrix
def test_everything_starts_pending_and_signals_flip_steps(onb_env):
    client = _admin()
    body = client.get("/v1/onboarding/status").json()
    steps = _steps(body)
    assert set(steps.values()) == {"pending"}
    assert body["data"]["completed"] is False

    # Signal 1: active tested connection.
    conn_id = _seed_connection()
    steps = _steps(client.get("/v1/onboarding/status").json())
    assert steps["connect_exchange"] == "done_auto"

    # The checklist never lies: revoking the connection flips it back.
    ConnectionStore().revoke(conn_id)
    steps = _steps(client.get("/v1/onboarding/status").json())
    assert steps["connect_exchange"] == "pending"

    # Signal 2: risk config touch.
    onb_env.log_decision("config_changed", {
        "actor": "root@x.dev", "scope": "risk",
        "before": {"max_daily_loss_pct": 5.0}, "after": {"max_daily_loss_pct": 4.0}})
    # Signal 3: agent touch.
    onb_env.log_decision("config_changed", {
        "actor": "root@x.dev", "scope": "agent:technical",
        "before": {"rsi": 30}, "after": {"rsi": 25}})
    # Signal 5: cycle activity.
    onb_env.log_signal("technical", {"action": "buy"})
    steps = _steps(client.get("/v1/onboarding/status").json())
    assert steps["risk_capital"] == "done_auto"
    assert steps["strategy_agents"] == "done_auto"
    assert steps["start_dryrun"] == "done_auto"
    assert steps["review"] == "pending"  # human by principle (no full brownfield)


def test_system_scope_only_counts_when_capital_changes(onb_env):
    """Nota 2 da revisão: an orchestrator-interval tweak must NOT mark the
    'Risco & capital' step; a capital change must."""
    client = _admin()
    onb_env.log_decision("config_changed", {
        "actor": "root@x.dev", "scope": "system",
        "before": {"orchestrator_interval_seconds": 60},
        "after": {"orchestrator_interval_seconds": 30}})
    steps = _steps(client.get("/v1/onboarding/status").json())
    assert steps["risk_capital"] == "pending"

    onb_env.log_decision("config_changed", {
        "actor": "root@x.dev", "scope": "system",
        "before": {"initial_capital": 10000.0}, "after": {"initial_capital": 20000.0}})
    steps = _steps(client.get("/v1/onboarding/status").json())
    assert steps["risk_capital"] == "done_auto"


# ------------------------------------------------------------- brownfield
def test_brownfield_running_system_is_born_completed(onb_env):
    """Nota 1 da revisão: a VPS that has run for months (connection + config
    touched + cycles in the ledger) must return completed=true on the very
    FIRST GET — the upgrade never opens the wizard."""
    _seed_connection()
    onb_env.log_decision("config_changed", {
        "actor": "root@x.dev", "scope": "risk", "before": {}, "after": {}})
    onb_env.log_decision("hitl_level_changed", {
        "level": 2, "previous_level": 1, "reason": "operação", "operator": "root@x.dev"})
    onb_env.log_signal("technical", {"action": "buy"})

    client = _admin()
    body = client.get("/v1/onboarding/status").json()["data"]
    assert body["completed"] is True
    assert body["completed_at"] is not None
    steps = {s["id"]: s for s in body["steps"]}
    assert steps["review"]["status"] == "done_auto"
    assert steps["review"]["detail"] == "sistema já em operação"
    events = onb_env.get_events("onboarding_completed")
    assert len(events) == 1  # stamped exactly once


# ------------------------------------------- persistence + acceptance 3
def test_skip_complete_dismiss_persist_and_completion_survives_restart(onb_env):
    client = _admin()
    for step in ("connect_exchange", "risk_capital", "strategy_agents", "start_dryrun"):
        assert client.patch("/v1/onboarding/status",
                            json={"step": step, "action": "skip"}).status_code == 200
    body = client.patch("/v1/onboarding/status",
                        json={"step": "review", "action": "complete"}).json()["data"]
    assert body["completed"] is True and body["completed_at"] is not None
    stamp = body["completed_at"]

    # "Restart": fresh app + fresh store instances over the same SQLite.
    deps.reset_singletons()
    fresh = _admin()
    body2 = fresh.get("/v1/onboarding/status").json()["data"]
    assert body2["completed"] is True
    assert body2["completed_at"] == stamp  # stamped once, never unset
    assert _steps({"data": body2})["review"] == "done_manual"

    # Dismiss persists too ("pular por agora").
    fresh.patch("/v1/onboarding/status", json={"dismiss": True})
    assert OnboardingStore().load()["dismissed"] is True

    # Unknown step / missing action → 422.
    assert fresh.patch("/v1/onboarding/status",
                       json={"step": "nope", "action": "skip"}).status_code == 422
    assert fresh.patch("/v1/onboarding/status",
                       json={"step": "review"}).status_code == 422


def test_summary_reflects_the_real_system(onb_env, monkeypatch):
    monkeypatch.setenv("ORDER_ROUTING", "paper")
    monkeypatch.setenv("SYMBOLS", "BTC/USDT,ETH/USDT")
    _seed_connection()
    body = _admin().get("/v1/onboarding/status").json()["data"]
    summary = body["summary"]
    assert summary["connection"]["label"] == "principal"
    assert summary["connection"]["testnet"] is True
    assert summary["routing"] == "paper"
    assert summary["pairs"] == "BTC/USDT,ETH/USDT"
    assert isinstance(summary["autonomy_level"], int)
    assert "max_daily_loss_pct" in summary["risk"]


# ------------------------------------------------------------------ gating
def test_only_admin_users_reach_the_guide(onb_env):
    operator = TestClient(create_app())
    assert operator.post("/v1/auth/login", json={
        "email": "op@x.dev", "password": "password-op"}).status_code == 200
    r = operator.get("/v1/onboarding/status")
    assert r.status_code == 403
    assert r.json()["required_permission"] == "manage_keys"

    anonymous = TestClient(create_app())
    assert anonymous.get("/v1/onboarding/status").status_code in (401, 403)


def test_machine_and_demo_are_excluded(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_MODE", "demo")
    monkeypatch.setenv("API_KEYS", "machine-key")
    deps.reset_singletons()
    init_db()
    client = TestClient(create_app())
    # Machine keys hold manage_keys, but the guide is for humans (declared).
    assert client.get("/v1/onboarding/status",
                      headers={"X-API-Key": "machine-key"}).status_code == 403
    assert client.get("/v1/onboarding/status").status_code == 403  # demo
    deps.reset_singletons()


def test_detection_unit_level_compute(tmp_path, monkeypatch):
    """compute_status works standalone (unit level, AUTH-independent)."""
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key-onboarding")  # gitleaks:allow (test fixture)
    deps.reset_singletons()
    init_db()
    ledger = deps.get_ledger()
    status = compute_status(ledger, ConnectionStore())
    assert status["completed"] is False
    assert all(s["status"] == "pending" for s in status["steps"])
    deps.reset_singletons()
