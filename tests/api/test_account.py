"""A2 account self-service: profile (e-mail immutable), password change with
A7 session revocation, and locale/timezone preferences on the boot probe."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.auth.store import UserStore
from src.core.db import init_db


@pytest.fixture
def acc_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_MODE", "required")
    monkeypatch.setenv("API_KEYS", "machine-key")
    deps.reset_singletons()
    init_db()
    from src.api.routes.auth import reset_login_limiter

    reset_login_limiter()
    users = UserStore()
    users.create("alice@x.dev", "password-alice", name="Alice", role="operador")  # gitleaks:allow (test fixture)
    yield users
    deps.reset_singletons()


def _client_as(email: str = "alice@x.dev", password: str = "password-alice") -> TestClient:
    client = TestClient(create_app())
    r = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return client


# -------------------------------------------------------------------- profile
def test_profile_roundtrip_and_email_is_immutable(acc_env):
    client = _client_as()
    me = client.get("/v1/account/profile").json()["data"]
    assert me["email"] == "alice@x.dev" and me["name"] == "Alice"

    r = client.patch("/v1/account/profile", json={
        "name": "Alice Prado", "job_title": "Operadora-chefe", "avatar_color": "violet",
    })
    assert r.status_code == 200, r.text
    out = r.json()["data"]
    assert (out["name"], out["job_title"], out["avatar_color"]) == \
        ("Alice Prado", "Operadora-chefe", "violet")

    # E-mail change is DEFERRED: an attempt is an explicit 422, never silent.
    assert client.patch("/v1/account/profile",
                        json={"email": "new@x.dev"}).status_code == 422
    assert client.get("/v1/account/profile").json()["data"]["email"] == "alice@x.dev"

    # Palette is token-derived and closed.
    assert client.patch("/v1/account/profile",
                        json={"avatar_color": "#ff0000"}).status_code == 422

    events = deps.get_ledger().get_events("auth_profile_updated")
    assert events and events[-1]["data"]["actor"] == "alice@x.dev"


# ------------------------------------------------------------------- password
def test_password_change_requires_current_and_revokes_others(acc_env):
    other = _client_as()          # second session (should die)
    client = _client_as()         # session performing the change (survives)

    assert client.patch("/v1/account/password", json={
        "current_password": "wrong", "new_password": "new-password-9",
    }).status_code == 401

    r = client.patch("/v1/account/password", json={
        "current_password": "password-alice", "new_password": "new-password-9",
    })
    assert r.status_code == 200, r.text
    assert r.json()["data"]["other_sessions_revoked"] == 1

    # A7 integration: the other session is dead, the current one survives.
    assert other.get("/v1/auth/me").json()["data"]["authenticated"] is False
    assert client.get("/v1/account/profile").status_code == 200

    # Old password no longer logs in; the new one does.
    probe = TestClient(create_app())
    assert probe.post("/v1/auth/login", json={
        "email": "alice@x.dev", "password": "password-alice"}).status_code == 401
    _client_as(password="new-password-9")

    events = deps.get_ledger().get_events("auth_password_changed")
    assert events and events[-1]["data"]["detail"] == "sessions_revoked=1"


# ---------------------------------------------------------------- preferences
def test_preferences_defaults_validation_and_me(acc_env):
    client = _client_as()
    prefs = client.get("/v1/account/preferences").json()["data"]
    assert prefs == {"locale": "pt-BR", "timezone": "auto",
                     "number_locale": "auto", "date_locale": "auto"}

    assert client.patch("/v1/account/preferences",
                        json={"timezone": "Mars/Olympus"}).status_code == 422
    assert client.patch("/v1/account/preferences",
                        json={"locale": "fr"}).status_code == 422
    assert client.patch("/v1/account/preferences",
                        json={"theme": "dark"}).status_code == 422  # out of scope

    r = client.patch("/v1/account/preferences", json={
        "locale": "en", "timezone": "America/Sao_Paulo",
        "number_locale": "en-US", "date_locale": "en-US",
    })
    assert r.status_code == 200, r.text
    assert r.json()["data"]["timezone"] == "America/Sao_Paulo"

    # Persisted, and the boot probe carries them (no extra request needed).
    me = client.get("/v1/auth/me").json()["data"]
    assert me["prefs"]["locale"] == "en"
    assert me["prefs"]["number_locale"] == "en-US"


# ----------------------------------------------------------------- gating
def test_account_routes_require_a_user_session(acc_env):
    anonymous = TestClient(create_app())
    machine = TestClient(create_app())
    for path in ("/v1/account/profile", "/v1/account/preferences"):
        assert anonymous.get(path).status_code == 401
        assert machine.get(path, headers={"X-API-Key": "machine-key"}).status_code == 401


def test_demo_mode_has_no_account(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_MODE", "demo")
    monkeypatch.delenv("API_KEYS", raising=False)
    deps.reset_singletons()
    init_db()
    client = TestClient(create_app())
    assert client.get("/v1/account/profile").status_code == 401
    deps.reset_singletons()
