"""A7 security self-service: session listing/revocation scoped to the owner,
own-email login history, and password-gated backup-code regeneration."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.auth.store import UserStore
from src.core.db import init_db


@pytest.fixture
def sec_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_MODE", "required")
    monkeypatch.setenv("API_KEYS", "machine-key")
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key-for-2fa")  # gitleaks:allow (test fixture)
    deps.reset_singletons()
    init_db()
    from src.api.routes.auth import reset_login_limiter

    reset_login_limiter()
    users = UserStore()
    users.create("alice@x.dev", "password-alice", role="operador")  # gitleaks:allow (test fixture)
    users.create("bob@x.dev", "password-bob", role="operador")  # gitleaks:allow (test fixture)
    yield users
    deps.reset_singletons()


def _client_as(email: str, password: str, ua: str = "pytest-ua") -> TestClient:
    client = TestClient(create_app(), headers={"User-Agent": ua})
    r = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return client


ALICE = ("alice@x.dev", "password-alice")
BOB = ("bob@x.dev", "password-bob")


# ------------------------------------------------------------------- sessions
def test_sessions_list_marks_the_current_one(sec_env):
    client = _client_as(*ALICE, ua="Mozilla/5.0 Chrome/126.0 pytest")
    rows = client.get("/v1/security/sessions").json()["data"]
    assert len(rows) == 1
    assert rows[0]["current"] is True
    assert rows[0]["user_agent"].startswith("Mozilla/5.0 Chrome")
    assert rows[0]["ip"]


def test_revoke_another_of_my_sessions(sec_env):
    first = _client_as(*ALICE)
    second = _client_as(*ALICE)
    rows = second.get("/v1/security/sessions").json()["data"]
    assert len(rows) == 2
    other_id = next(r["id"] for r in rows if not r["current"])

    r = second.delete(f"/v1/security/sessions/{other_id}")
    assert r.status_code == 200
    assert r.json()["data"] == {"revoked": True, "current": False}
    # The revoked session is dead immediately.
    assert first.get("/v1/auth/me").json()["data"]["authenticated"] is False
    # And the survivor still works.
    assert second.get("/v1/security/sessions").status_code == 200


def test_someone_elses_session_id_is_a_404(sec_env):
    alice = _client_as(*ALICE)
    bob = _client_as(*BOB)
    bob_id = bob.get("/v1/security/sessions").json()["data"][0]["id"]
    r = alice.delete(f"/v1/security/sessions/{bob_id}")
    assert r.status_code == 404
    assert r.json()["error"] == "session_not_found"
    # Bob is untouched.
    assert bob.get("/v1/auth/me").json()["data"]["authenticated"] is True


def test_revoke_others_keeps_only_the_current(sec_env):
    _client_as(*ALICE)
    _client_as(*ALICE)
    mine = _client_as(*ALICE)
    r = mine.post("/v1/security/sessions/revoke-others", json={})
    assert r.status_code == 200
    assert r.json()["data"]["revoked"] == 2
    rows = mine.get("/v1/security/sessions").json()["data"]
    assert len(rows) == 1 and rows[0]["current"] is True
    events = deps.get_ledger().get_events("auth_sessions_revoked_others")
    assert events and events[-1]["data"]["actor"] == "alice@x.dev"


def test_sessions_require_a_user_session(sec_env):
    anonymous = TestClient(create_app())
    assert anonymous.get("/v1/security/sessions").status_code == 401
    machine = TestClient(create_app())
    r = machine.get("/v1/security/sessions", headers={"X-API-Key": "machine-key"})
    assert r.status_code == 401  # machine keys have no session to manage


# ------------------------------------------------------------- login history
def test_login_history_is_scoped_to_my_email(sec_env):
    # A failed attempt for alice, then real logins for alice and bob.
    probe = TestClient(create_app())
    assert probe.post("/v1/auth/login", json={
        "email": "alice@x.dev", "password": "wrong-password"}).status_code == 401
    alice = _client_as(*ALICE)
    _client_as(*BOB)

    body = alice.get("/v1/security/logins").json()
    assert body["meta"]["total"] == 2  # the failure + the success; bob absent
    actors = {e["actor"] for e in body["data"]}
    assert actors == {"alice@x.dev"}
    results = sorted(e["success"] for e in body["data"])
    assert results == [False, True]
    assert all(e["action"] == "login" for e in body["data"])
    assert all(e["ip"] for e in body["data"])


# ------------------------------------------------- 2FA backup regeneration
def _enable_2fa(client: TestClient) -> list:
    import pyotp

    setup = client.post("/v1/auth/2fa/setup", json={}).json()["data"]
    code = pyotp.TOTP(setup["secret"]).now()
    r = client.post("/v1/auth/2fa/enable", json={"code": code})
    assert r.status_code == 200, r.text
    return r.json()["data"]["backup_codes"]


def test_backup_regenerate_requires_password_and_burns_old_codes(sec_env):
    client = _client_as(*ALICE)
    old_codes = _enable_2fa(client)

    r = client.post("/v1/auth/2fa/backup/regenerate", json={"password": "wrong"})
    assert r.status_code == 401

    r = client.post("/v1/auth/2fa/backup/regenerate",
                    json={"password": "password-alice"})
    assert r.status_code == 200, r.text
    new_codes = r.json()["data"]["backup_codes"]
    assert len(new_codes) == 10
    assert set(new_codes).isdisjoint(old_codes)

    # Old code no longer unlocks a 2FA login; a new one does.
    def _challenge():
        fresh = TestClient(create_app())
        resp = fresh.post("/v1/auth/login", json={
            "email": "alice@x.dev", "password": "password-alice"}).json()["data"]
        assert resp["two_factor_required"] is True
        return fresh, resp["challenge"]

    fresh, challenge = _challenge()
    assert fresh.post("/v1/auth/2fa/verify", json={
        "challenge": challenge, "code": old_codes[0]}).status_code == 401
    fresh, challenge = _challenge()
    assert fresh.post("/v1/auth/2fa/verify", json={
        "challenge": challenge, "code": new_codes[0]}).status_code == 200

    events = deps.get_ledger().get_events("auth_2fa_backup_regenerated")
    assert events and events[-1]["data"]["actor"] == "alice@x.dev"


def test_backup_regenerate_needs_2fa_enabled(sec_env):
    client = _client_as(*BOB)
    r = client.post("/v1/auth/2fa/backup/regenerate",
                    json={"password": "password-bob"})
    assert r.status_code == 400
    assert r.json()["error"] == "totp_not_enabled"
