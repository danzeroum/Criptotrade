"""A5: exchange connections (secret never leaves, real read-only test, live
gate in the factory) and platform API keys (hash-only, scoped, label as the
ledger actor). Includes the NEGATIVE leak test: a provider error containing
the secret must come out redacted in the response, the ledger and the logs."""
from __future__ import annotations

import logging
import sqlite3

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.core.db import get_db_path, init_db
from src.core.exchange_factory import build_exchange_client
from src.exchanges.store import ConnectionStore, PlatformKeyStore

SECRET = "super-secret-value-9f8e7d6c"  # gitleaks:allow (test fixture)
API_KEY = "exchange-key-abcd1234"  # gitleaks:allow (test fixture)


@pytest.fixture
def conn_env(tmp_path, monkeypatch):
    """AUTH_MODE=off (legacy pass on require_perm) + fresh db."""
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key-connections")  # gitleaks:allow (test fixture)
    monkeypatch.delenv("AUTH_MODE", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.delenv("ORDER_ROUTING", raising=False)
    monkeypatch.setenv("EXCHANGE_DRY_RUN", "true")
    deps.reset_singletons()
    init_db()
    yield ConnectionStore()
    deps.reset_singletons()


def _client() -> TestClient:
    return TestClient(create_app())


def _create(client, scope="read", confirm=None, label="Binance principal"):
    body = {
        "exchange_id": "binance", "label": label,
        "api_key": API_KEY, "api_secret": SECRET,
        "scope": scope, "testnet": True,
    }
    if confirm is not None:
        body["confirm"] = confirm
    return client.post("/v1/exchanges/connect", json=body)


class _FakeBinance:
    """Offline ccxt stand-in for the connection tester."""

    balance = {"info": {"canTrade": True}, "total": {}}
    error: Exception | None = None
    last_init = None

    def __init__(self, config):
        type(self).last_init = config
        self.sandbox = False

    def set_sandbox_mode(self, flag):
        self.sandbox = flag

    def fetch_balance(self):
        if type(self).error is not None:
            raise type(self).error
        return type(self).balance


@pytest.fixture
def fake_ccxt(monkeypatch):
    import ccxt

    _FakeBinance.error = None
    _FakeBinance.balance = {"info": {"canTrade": True}, "total": {}}
    monkeypatch.setattr(ccxt, "binance", _FakeBinance)
    return _FakeBinance


# ----------------------------------------------- aceite 1: secret nunca sai
def test_secret_is_encrypted_and_never_returned(conn_env):
    client = _client()
    r = _create(client)
    assert r.status_code == 201, r.text
    out = r.json()["data"]
    assert out["api_key_masked"] == "•••1234"
    assert SECRET not in r.text  # not even masked — the secret NEVER returns

    with sqlite3.connect(get_db_path()) as conn:
        (config_enc,) = conn.execute(
            "SELECT config_enc FROM exchange_connections WHERE id = ?", (out["id"],)
        ).fetchone()
    assert SECRET not in config_enc and API_KEY not in config_enc

    listed = client.get("/v1/exchanges/connections")
    assert SECRET not in listed.text and API_KEY not in listed.text

    # Rotate: keeps the id, swaps the secret, RESETS the test status.
    conn_env.record_test(out["id"], True, {"read_ok": True})
    r2 = client.post(f"/v1/exchanges/{out['id']}/rotate",
                     json={"api_secret": "new-secret-value-123456"})
    assert r2.status_code == 200
    assert "new-secret-value" not in r2.text
    assert r2.json()["data"]["last_test_ok"] is None
    stored = conn_env.config(conn_env.get(out["id"]))
    assert stored["api_secret"] == "new-secret-value-123456"


def test_provider_error_containing_secret_is_redacted_everywhere(
        conn_env, fake_ccxt, caplog):
    client = _client()
    conn_id = _create(client).json()["data"]["id"]
    fake_ccxt.error = RuntimeError(
        f"binance rejected signature for key {API_KEY} secret {SECRET}"
    )
    with caplog.at_level(logging.DEBUG):
        r = client.post(f"/v1/exchanges/{conn_id}/test")
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["ok"] is False
    # The real reason survives; the credentials do not — anywhere.
    assert "rejected signature" in body["error"]
    assert SECRET not in r.text and API_KEY not in r.text
    assert SECRET not in caplog.text and API_KEY not in caplog.text
    events = deps.get_ledger().get_events("connection_tested")
    assert events and SECRET not in str(events[-1]) and API_KEY not in str(events[-1])


# ------------------------------------ aceite 2: teste real com permissões
def test_connection_test_detects_permissions(conn_env, fake_ccxt):
    client = _client()
    conn_id = _create(client).json()["data"]["id"]
    r = client.post(f"/v1/exchanges/{conn_id}/test")
    assert r.status_code == 200
    body = r.json()["data"]
    assert body == {"ok": True, "read_ok": True, "trade_detected": True}
    # Sandbox honored (testnet=True) and creds passed to ccxt, never an order.
    assert fake_ccxt.last_init["apiKey"] == API_KEY
    row = conn_env.get(conn_id)
    assert row["last_test_ok"] == 1

    # Exchange without canTrade info → honestly "not verifiable" (None).
    fake_ccxt.balance = {"info": {}, "total": {}}
    body = client.post(f"/v1/exchanges/{conn_id}/test").json()["data"]
    assert body["trade_detected"] is None


def test_trade_scope_requires_typed_confirmation(conn_env):
    client = _client()
    assert _create(client, scope="trade").status_code == 422
    assert _create(client, scope="trade", confirm="trade").status_code == 422
    r = _create(client, scope="trade", confirm="TRADE")
    assert r.status_code == 201
    assert r.json()["data"]["scope"] == "trade"


# --------------------------------------------- aceite 3: gate do modo live
def test_live_gate_in_the_factory(conn_env, monkeypatch):
    client = _client()
    monkeypatch.setenv("EXCHANGE_DRY_RUN", "false")
    monkeypatch.setenv("ORDER_ROUTING", "live")

    # No connection at all → refuse to boot.
    with pytest.raises(RuntimeError, match="conexão de exchange ATIVA"):
        build_exchange_client()

    # Active but read-only → refuse, naming the scope.
    read_id = _create(client, label="somente-leitura").json()["data"]["id"]
    conn_env.activate(read_id)
    conn_env.record_test(read_id, True, {"read_ok": True})
    with pytest.raises(RuntimeError, match="escopo 'read'"):
        build_exchange_client()

    # Trade but untested (e.g. just rotated) → refuse until re-tested.
    trade_id = _create(client, scope="trade", confirm="TRADE",
                       label="prod").json()["data"]["id"]
    conn_env.activate(trade_id)
    with pytest.raises(RuntimeError, match="teste de conexão OK"):
        build_exchange_client()

    # Tested trade connection → boots with the DB credentials.
    conn_env.record_test(trade_id, True, {"read_ok": True, "trade_detected": True})
    exchange_client = build_exchange_client()
    assert exchange_client.exchange is not None
    assert exchange_client.exchange.apiKey == API_KEY


def test_live_boot_logs_the_destination(conn_env, monkeypatch, caplog):
    client = _client()
    trade_id = _create(client, scope="trade", confirm="TRADE",
                       label="staging").json()["data"]["id"]
    conn_env.activate(trade_id)
    conn_env.record_test(trade_id, True, {"read_ok": True})
    monkeypatch.setenv("EXCHANGE_DRY_RUN", "false")
    monkeypatch.setenv("ORDER_ROUTING", "live")
    with caplog.at_level(logging.WARNING):
        build_exchange_client()
    # Nota 1 da revisão: uma linha inconfundível dizendo para onde aponta.
    assert 'LIVE routing → BINANCE TESTNET (conexão "staging")' in caplog.text


def test_empty_table_keeps_env_fallback_bit_compatible(conn_env, monkeypatch):
    monkeypatch.setenv("EXCHANGE_DRY_RUN", "true")
    client = build_exchange_client()
    assert client.dry_run is True and client.exchange is None


# ------------------------------------------------------------ platform keys
def test_platform_key_shown_once_scoped_and_stamped(conn_env):
    client = _client()
    r = client.post("/v1/api-keys", json={"label": "grafana-readonly",
                                          "scope": "visualizador"})
    assert r.status_code == 201, r.text
    created = r.json()["data"]
    token = created["key"]
    assert token.startswith("ctk_") and created["key_prefix"] == token[:12]

    # Listing never carries the key again — only the display prefix.
    listing = client.get("/v1/api-keys")
    assert token not in listing.text
    assert listing.json()["data"][0]["key_prefix"] == token[:12]

    # In disk: hash only.
    with sqlite3.connect(get_db_path()) as conn:
        (key_hash,) = conn.execute(
            "SELECT key_hash FROM platform_api_keys").fetchone()
    assert token not in key_hash

    # The key authenticates with its SCOPE: visualizador-machine reads /me but
    # cannot approve orders (approve_order needs operador+).
    me = client.get("/v1/auth/me", headers={"X-API-Key": token}).json()["data"]
    assert me["authenticated"] is True
    assert me["permissions"] == []
    assert PlatformKeyStore().list()[0]["last_used_at"] is not None


def test_platform_key_actor_is_the_label_and_revoke_kills_it(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key-connections")  # gitleaks:allow (test fixture)
    monkeypatch.setenv("AUTH_MODE", "required")
    monkeypatch.delenv("API_KEYS", raising=False)
    deps.reset_singletons()
    init_db()
    keys = PlatformKeyStore()
    row, token = keys.create("bot-admin", "admin", "root@x.dev")

    client = TestClient(create_app())
    headers = {"X-API-Key": token}
    r = client.patch("/v1/config", json={"initial_capital": 31337},
                     headers=headers)
    assert r.status_code == 200, r.text
    # A4 upgrade: the ledger actor is the key's LABEL, not generic "api-key".
    event = deps.get_ledger().get_events("config_changed")[-1]
    assert event["data"]["actor"] == "bot-admin"

    # Machine keys NEVER manage users, whatever the scope.
    assert client.get("/v1/users", headers=headers).status_code == 403

    keys.revoke(row["id"])
    assert client.get("/v1/metrics", headers=headers).status_code == 401
    from src.api.routes import config as config_route

    config_route._runtime_overrides.clear()
    deps.reset_singletons()


def test_db_key_passes_the_legacy_env_gate(tmp_path, monkeypatch):
    """AUTH_MODE=off + API_KEYS set: a DB platform key must pass the legacy
    middleware gate exactly like an env key; garbage still gets the 401."""
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key-connections")  # gitleaks:allow (test fixture)
    monkeypatch.delenv("AUTH_MODE", raising=False)
    monkeypatch.setenv("API_KEYS", "legacy-env-key")
    deps.reset_singletons()
    init_db()
    _, token = PlatformKeyStore().create("integração", "visualizador", "root")
    client = TestClient(create_app())
    assert client.get("/v1/metrics", headers={"X-API-Key": "legacy-env-key"}).status_code == 200
    assert client.get("/v1/metrics", headers={"X-API-Key": token}).status_code == 200
    assert client.get("/v1/metrics", headers={"X-API-Key": "garbage"}).status_code == 401
    assert client.get("/v1/metrics").status_code == 401
    deps.reset_singletons()


def test_connections_require_manage_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key-connections")  # gitleaks:allow (test fixture)
    monkeypatch.setenv("AUTH_MODE", "required")
    monkeypatch.delenv("API_KEYS", raising=False)
    deps.reset_singletons()
    init_db()
    from src.api.routes.auth import reset_login_limiter

    reset_login_limiter()
    from src.auth.store import UserStore

    UserStore().create("op@x.dev", "password-op", role="operador")  # gitleaks:allow (test fixture)
    client = TestClient(create_app())
    assert client.post("/v1/auth/login", json={
        "email": "op@x.dev", "password": "password-op"}).status_code == 200
    r = client.get("/v1/exchanges/connections")
    assert r.status_code == 403
    assert r.json()["required_permission"] == "manage_keys"
    deps.reset_singletons()
