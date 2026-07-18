"""A1 authentication: login, cookies, 2FA, refresh rotation, reset, bootstrap."""
from __future__ import annotations

import pyotp
import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.auth.store import UserStore, bootstrap_admin
from src.core.db import init_db


@pytest.fixture
def auth_env(tmp_path, monkeypatch):
    """Isolated auth db + secret key; singletons rebound to tmp_path."""
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key")
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.delenv("AUTH_MODE", raising=False)
    deps.reset_singletons()
    init_db()
    from src.api.routes.auth import reset_login_limiter

    reset_login_limiter()  # module-level limiter persists across tests otherwise
    yield tmp_path
    deps.reset_singletons()


@pytest.fixture
def client(auth_env):
    return TestClient(create_app())


@pytest.fixture
def user(auth_env):
    return UserStore().create("op@criptotrade.dev", "s3cret-pass", name="Op")


def _login(client, email="op@criptotrade.dev", password="s3cret-pass", **kw):
    return client.post("/v1/auth/login", json={"email": email, "password": password, **kw})


# ------------------------------------------------------------------ login
def test_login_sets_httponly_cookies(client, user):
    r = _login(client)
    assert r.status_code == 200
    assert r.json()["data"]["user"]["email"] == "op@criptotrade.dev"
    set_cookie = ";".join(r.headers.get_list("set-cookie")).lower()
    assert "ct_session=" in set_cookie and "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "ct_refresh=" in set_cookie


def test_wrong_password_and_unknown_email_are_indistinguishable(client, user):
    r1 = _login(client, password="wrong-password")
    r2 = _login(client, email="ghost@nowhere.dev", password="anything")
    assert r1.status_code == r2.status_code == 401
    assert r1.json() == r2.json()  # identical body: no enumeration signal


def test_login_rate_limited_per_email(client, user):
    for _ in range(5):
        _login(client, password="wrong-password")
    r = _login(client, password="wrong-password")
    assert r.status_code == 429


def test_failed_login_hits_the_ledger(client, user, auth_env):
    _login(client, password="wrong-password")
    events = deps.get_ledger().get_events("auth_login")
    assert any(e["data"]["success"] is False for e in events)


# ------------------------------------------------------------------ session
def test_me_reflects_session(client, user):
    _login(client)
    me = client.get("/v1/auth/me").json()["data"]
    assert me["authenticated"] is True
    assert me["user"]["email"] == "op@criptotrade.dev"


def test_logout_clears_and_invalidates(client, user, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "required")
    _login(client)
    assert client.get("/v1/metrics?period=all").status_code == 200
    client.post("/v1/auth/logout", json={})
    # The old cookie was revoked server-side (and cleared client-side).
    assert client.get("/v1/metrics?period=all").status_code == 401


def test_refresh_rotates_and_detects_reuse(client, user):
    _login(client)
    old_refresh = client.cookies.get("ct_refresh")
    r1 = client.post("/v1/auth/refresh")
    assert r1.status_code == 200
    new_refresh = client.cookies.get("ct_refresh")
    assert new_refresh and new_refresh != old_refresh

    # Replaying the pre-rotation token revokes the whole family.
    client.cookies.set("ct_refresh", old_refresh)
    assert client.post("/v1/auth/refresh").status_code == 401
    client.cookies.set("ct_refresh", new_refresh)
    assert client.post("/v1/auth/refresh").status_code == 401  # family dead
    # Both replays are theft signals (the second hits an already-revoked row).
    reuse = deps.get_ledger().get_events("auth_session_refresh_reuse")
    assert len(reuse) >= 1


# ------------------------------------------------------------------ 2FA
def test_2fa_full_flow_and_backup_code_single_use(client, user):
    _login(client)
    setup = client.post("/v1/auth/2fa/setup", json={}).json()["data"]
    code = pyotp.TOTP(setup["secret"]).now()
    enable = client.post("/v1/auth/2fa/enable", json={"code": code}).json()["data"]
    backup_codes = enable["backup_codes"]
    assert len(backup_codes) == 10

    client.post("/v1/auth/logout", json={})
    r = _login(client)
    assert r.json()["data"]["two_factor_required"] is True
    challenge = r.json()["data"]["challenge"]

    r2 = client.post("/v1/auth/2fa/verify",
                     json={"challenge": challenge, "code": backup_codes[0]})
    assert r2.status_code == 200
    assert r2.json()["data"]["backup_code_used"] is True
    assert r2.json()["data"]["remaining"] == 9

    # The same backup code cannot be used twice.
    client.post("/v1/auth/logout", json={})
    challenge2 = _login(client).json()["data"]["challenge"]
    r3 = client.post("/v1/auth/2fa/verify",
                     json={"challenge": challenge2, "code": backup_codes[0]})
    assert r3.status_code == 401


# ------------------------------------------------------------ password reset
def test_forgot_is_generic_and_reset_is_single_use(client, user, auth_env):
    r_known = client.post("/v1/auth/password/forgot", json={"email": "op@criptotrade.dev"})
    r_ghost = client.post("/v1/auth/password/forgot", json={"email": "ghost@nowhere.dev"})
    assert r_known.status_code == r_ghost.status_code == 200
    assert r_known.json() == r_ghost.json()

    token = UserStore().create_reset(user["id"])
    r = client.post("/v1/auth/password/reset",
                    json={"token": token, "new_password": "new-pass-123"})
    assert r.status_code == 200
    assert _login(client, password="new-pass-123").status_code == 200
    # Single use.
    r2 = client.post("/v1/auth/password/reset",
                     json={"token": token, "new_password": "other-pass-123"})
    assert r2.status_code == 400


# ------------------------------------------------------------------ bootstrap
def test_bootstrap_admin_is_one_shot(auth_env, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "root@criptotrade.dev")
    monkeypatch.setenv("ADMIN_PASSWORD", "boot-pass-123")
    store = UserStore()
    assert bootstrap_admin(store) is not None
    assert store.count() == 1
    # Non-empty table: seeding again (even with a different email) is inert.
    monkeypatch.setenv("ADMIN_EMAIL", "other@criptotrade.dev")
    assert bootstrap_admin(store) is None
    assert store.count() == 1
