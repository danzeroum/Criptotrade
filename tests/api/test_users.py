"""A3 user management: invite lifecycle, role/status changes, last-admin guard."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.auth.store import UserStore
from src.core.db import init_db


@pytest.fixture
def admin_client(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_MODE", "required")
    monkeypatch.delenv("API_KEYS", raising=False)
    deps.reset_singletons()
    init_db()
    from src.api.routes.auth import reset_login_limiter

    reset_login_limiter()
    UserStore().create("root@x.dev", "password-root", role="admin")
    client = TestClient(create_app())
    r = client.post("/v1/auth/login",
                    json={"email": "root@x.dev", "password": "password-root"})
    assert r.status_code == 200
    yield client
    deps.reset_singletons()


def test_invite_lifecycle(admin_client):
    r = admin_client.post("/v1/users/invite",
                          json={"email": "novo@x.dev", "role": "operador"})
    assert r.status_code == 201
    invite_id = r.json()["data"]["id"]

    # Pending invite shows up in the users list.
    listed = admin_client.get("/v1/users").json()["data"]
    pending = [u for u in listed if u["status"] == "pending"]
    assert pending and pending[0]["email"] == "novo@x.dev"

    # Accept with the token → active user with the invited role.
    token = UserStore().refresh_invite(invite_id)  # rotate to get a known token
    r2 = TestClient(create_app()).post("/v1/auth/invite/accept", json={
        "token": token, "name": "Novo Op", "password": "senha-nova-123",  # gitleaks:allow (test fixture)
    })
    assert r2.status_code == 200
    user = UserStore().get_by_email("novo@x.dev")
    assert user["role"] == "operador" and user["status"] == "active"

    # Token is single-use.
    r3 = TestClient(create_app()).post("/v1/auth/invite/accept", json={
        "token": token, "name": "X", "password": "outra-senha-123",  # gitleaks:allow (test fixture)
    })
    assert r3.status_code == 400


def test_revoked_invite_cannot_be_accepted(admin_client):
    admin_client.post("/v1/users/invite",
                      json={"email": "rev@x.dev", "role": "visualizador"})
    invite = UserStore().list_invites()[0]
    token = UserStore().refresh_invite(invite["id"])
    admin_client.delete(f"/v1/users/invites/{invite['id']}")
    r = TestClient(create_app()).post("/v1/auth/invite/accept", json={
        "token": token, "name": "X", "password": "senha-revogada-1",  # gitleaks:allow (test fixture)
    })
    assert r.status_code == 400


def test_duplicate_invite_email_conflicts(admin_client):
    assert admin_client.post(
        "/v1/users/invite", json={"email": "root@x.dev", "role": "admin"}
    ).status_code == 409


def test_role_and_status_changes(admin_client):
    other = UserStore().create("op2@x.dev", "password-op2", role="operador")
    r = admin_client.patch(f"/v1/users/{other['id']}/role", json={"role": "admin"})
    assert r.status_code == 200 and r.json()["data"]["role"] == "admin"

    r2 = admin_client.patch(f"/v1/users/{other['id']}/status",
                            json={"status": "suspended"})
    assert r2.status_code == 200 and r2.json()["data"]["status"] == "suspended"
    # Suspended user cannot log in (indistinguishable 401).
    r3 = TestClient(create_app()).post(
        "/v1/auth/login", json={"email": "op2@x.dev", "password": "password-op2"}
    )
    assert r3.status_code == 401


def test_last_admin_is_protected(admin_client):
    root = UserStore().get_by_email("root@x.dev")
    assert admin_client.patch(f"/v1/users/{root['id']}/role",
                              json={"role": "operador"}).status_code == 409
    assert admin_client.patch(f"/v1/users/{root['id']}/status",
                              json={"status": "suspended"}).status_code == 409
    assert admin_client.delete(f"/v1/users/{root['id']}").status_code == 409


def test_users_audit_events_reach_the_ledger(admin_client):
    admin_client.post("/v1/users/invite",
                      json={"email": "aud@x.dev", "role": "visualizador"})
    events = deps.get_ledger().get_events("auth_user_invited")
    assert events and events[-1]["data"]["actor"] == "root@x.dev"
