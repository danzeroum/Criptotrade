"""A3 RBAC: per-permission enforcement, machine bypass, real operator stamping."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.auth.store import UserStore
from src.core.db import init_db


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
    users = UserStore()
    users.create("viewer@x.dev", "password-viewer", role="visualizador")
    users.create("op@x.dev", "password-op", role="operador")
    users.create("root@x.dev", "password-root", role="admin")
    yield users
    deps.reset_singletons()


def _client_as(email: str, password: str) -> TestClient:
    client = TestClient(create_app())
    r = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return client


VIEWER = ("viewer@x.dev", "password-viewer")
OPERATOR = ("op@x.dev", "password-op")
ADMIN = ("root@x.dev", "password-root")


# ------------------------------------------------- permission matrix per route
def test_autonomy_patch_permission_matrix(rbac_env):
    body = {"level": 1, "reason": "ajuste de teste"}
    r = _client_as(*VIEWER).patch("/v1/hitl/config", json=body)
    assert r.status_code == 403
    assert r.json()["required_permission"] == "change_autonomy"

    assert _client_as(*OPERATOR).patch("/v1/hitl/config", json=body).status_code == 200
    assert _client_as(*ADMIN).patch("/v1/hitl/config", json=body).status_code == 200


def test_risk_and_settings_are_admin_only(rbac_env):
    risk_body = {"confirm": True, "max_position_size_pct": 4.0}
    for creds in (VIEWER, OPERATOR):
        assert _client_as(*creds).patch("/v1/risk/config", json=risk_body).status_code == 403
        assert _client_as(*creds).patch(
            "/v1/config", json={"initial_capital": 20000}
        ).status_code == 403
    assert _client_as(*ADMIN).patch(
        "/v1/config", json={"initial_capital": 20000}
    ).status_code == 200


def test_machine_key_bypasses_role_gates_but_not_user_mgmt(rbac_env):
    client = TestClient(create_app())
    headers = {"X-API-Key": "machine-key"}
    assert client.patch("/v1/hitl/config", json={"level": 1, "reason": "ajuste automatico"},
                        headers=headers).status_code == 200
    # manage_users is deliberately withheld from machine keys.
    assert client.get("/v1/users", headers=headers).status_code == 403


def test_me_returns_role_permissions(rbac_env):
    me = _client_as(*OPERATOR).get("/v1/auth/me").json()["data"]
    assert "approve_order" in me["permissions"]
    assert "manage_users" not in me["permissions"]


def test_roles_endpoint_serves_the_matrix(rbac_env):
    roles = _client_as(*VIEWER).get("/v1/roles").json()["data"]
    by_id = {r["id"]: r for r in roles}
    assert set(by_id) == {"visualizador", "operador", "admin"}
    assert by_id["visualizador"]["permissions"] == []
    assert "manage_users" in by_id["admin"]["permissions"]


# ------------------------------------------------------------ operator stamping
def test_approve_stamps_the_logged_in_user(rbac_env):
    client = _client_as(*OPERATOR)
    r = client.post("/v1/orders", json={
        "pair": "BTC/USDT", "side": "buy", "quantity": 0.05, "price": 50_000.0,
        "strategy": "grid", "agent_id": "test", "confidence": 0.9,
        "critical": True,  # forces pending (never auto-approved)
        "reason": "teste de stamping", "stop_loss": 48_500.0, "position_size_pct": 2.0,
    })
    assert r.status_code == 202, r.text
    order_id = r.json()["data"]["id"]

    # The client-sent operator is overridden by the authenticated identity.
    r2 = client.patch(f"/v1/orders/{order_id}/status",
                      json={"decision": "approve", "operator": "spoofed-name"})
    assert r2.status_code in (200, 201), r2.text
    assert r2.json()["data"]["operator_id"] == "op@x.dev"

    events = deps.get_ledger().get_events("hitl_approval")
    assert events and events[-1]["data"]["user"] == "op@x.dev"


def test_auth_mode_off_keeps_client_operator(tmp_path, monkeypatch):
    """Legacy path: no sessions, patch.operator is still honored."""
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.delenv("AUTH_MODE", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)
    deps.reset_singletons()
    init_db()
    client = TestClient(create_app())
    r = client.post("/v1/orders", json={
        "pair": "BTC/USDT", "side": "buy", "quantity": 0.05, "price": 50_000.0,
        "strategy": "grid", "agent_id": "test", "confidence": 0.9,
        "critical": True, "reason": "teste legado", "stop_loss": 48_500.0, "position_size_pct": 2.0,
    })
    assert r.status_code == 202
    order_id = r.json()["data"]["id"]
    r2 = client.patch(f"/v1/orders/{order_id}/status",
                      json={"decision": "approve", "operator": "legacy-op"})
    assert r2.status_code in (200, 201)
    assert r2.json()["data"]["operator_id"] == "legacy-op"
    deps.reset_singletons()
