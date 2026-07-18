"""AUTH_MODE matrix (D4/D5): off is bit-compatible, demo is read-only, required gates."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.auth.store import UserStore
from src.core.db import init_db


@pytest.fixture
def auth_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.delenv("AUTH_MODE", raising=False)
    deps.reset_singletons()
    init_db()
    from src.api.routes.auth import reset_login_limiter

    reset_login_limiter()
    yield
    deps.reset_singletons()


def test_off_without_keys_everything_open(auth_env):
    client = TestClient(create_app())
    assert client.get("/v1/metrics?period=all").status_code == 200


def test_off_with_keys_keeps_legacy_401(auth_env, monkeypatch):
    monkeypatch.setenv("API_KEYS", "k1")
    client = TestClient(create_app())
    assert client.get("/v1/metrics?period=all").status_code == 401
    assert client.get("/v1/metrics?period=all", headers={"X-API-Key": "k1"}).status_code == 200
    # Auth endpoints stay public even with keys set (the browser has none yet).
    assert client.get("/v1/auth/me").status_code == 200


def test_required_rejects_anonymous_allows_key_and_session(auth_env, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "required")
    monkeypatch.setenv("API_KEYS", "k1")
    UserStore().create("op@criptotrade.dev", "s3cret-pass")
    client = TestClient(create_app())

    assert client.get("/v1/metrics?period=all").status_code == 401
    assert client.get("/v1/metrics?period=all", headers={"X-API-Key": "k1"}).status_code == 200

    r = client.post("/v1/auth/login",
                    json={"email": "op@criptotrade.dev", "password": "s3cret-pass"})
    assert r.status_code == 200
    assert client.get("/v1/metrics?period=all").status_code == 200  # cookie session


def test_demo_resolves_read_only_visualizador(auth_env, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "demo")
    client = TestClient(create_app())
    me = client.get("/v1/auth/me").json()["data"]
    assert me["mode"] == "demo"
    assert me["authenticated"] is False
    assert me["user"]["role"] == "visualizador"
    # Reads are open in demo.
    assert client.get("/v1/metrics?period=all").status_code == 200


def test_cookie_writes_require_json_content_type(auth_env, monkeypatch):
    """CSRF guard: session-authenticated writes must be application/json."""
    monkeypatch.setenv("AUTH_MODE", "required")
    UserStore().create("op@criptotrade.dev", "s3cret-pass")
    client = TestClient(create_app())
    client.post("/v1/auth/login",
                json={"email": "op@criptotrade.dev", "password": "s3cret-pass"})
    r = client.post(
        "/v1/hitl/config",  # any guarded write path works for the check
        content="level=3",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code in (403, 405)  # 403 from the CSRF guard (405 if method absent)
