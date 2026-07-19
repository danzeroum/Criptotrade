"""N1 — GET /v1/pairs: the dynamic pair source for the selector.

Operated (env SYMBOLS ∩ allowlist) vs observable (MARKET_PAIRS allowlist), the
per-symbol last-cycle freshness from the ledger, the env-reflects-without-restart
contract (the aceite), and demo read access (read-only, no secrets).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.core.db import init_db


@pytest.fixture
def pairs_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.delenv("AUTH_MODE", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.setenv("MARKET_PAIRS", "BTC/USDT,ETH/USDT,SOL/USDT,XRP/USDT")
    monkeypatch.setenv("SYMBOLS", "BTC/USDT,ETH/USDT")
    init_db()
    yield deps.get_ledger()


def _get(client: TestClient) -> dict:
    r = client.get("/v1/pairs")
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_operated_vs_observable_split(pairs_env):
    data = _get(TestClient(create_app()))
    operados = [p["symbol"] for p in data["operados"]]
    assert operados == ["BTC/USDT", "ETH/USDT"]           # SYMBOLS ∩ allowlist
    assert data["observaveis"] == ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"]
    # operated ⊆ observable by construction
    assert set(operados) <= set(data["observaveis"])


def test_last_cycle_status_from_ledger(pairs_env):
    ledger = pairs_env
    ledger.log_signal(agent="strategy", signal={"symbol": "BTC/USDT", "action": "buy"})

    data = _get(TestClient(create_app()))
    by_sym = {p["symbol"]: p for p in data["operados"]}
    assert by_sym["BTC/USDT"]["status"] == "operando"
    assert by_sym["BTC/USDT"]["last_cycle_at"] is not None
    # ETH has no signal yet → still awaiting its first cycle.
    assert by_sym["ETH/USDT"]["status"] == "aguardando"
    assert by_sym["ETH/USDT"]["last_cycle_at"] is None


def test_env_change_is_reflected_without_restart(pairs_env, monkeypatch):
    # The aceite: change SYMBOLS and a fresh request reflects it (no front edit).
    monkeypatch.setenv("SYMBOLS", "BTC/USDT,SOL/USDT,XRP/USDT")
    data = _get(TestClient(create_app()))
    assert [p["symbol"] for p in data["operados"]] == ["BTC/USDT", "SOL/USDT", "XRP/USDT"]


def test_invalid_symbols_are_dropped(pairs_env, monkeypatch):
    monkeypatch.setenv("SYMBOLS", "BTC/USDT,DOGE/USDT")  # DOGE not in allowlist
    data = _get(TestClient(create_app()))
    assert [p["symbol"] for p in data["operados"]] == ["BTC/USDT"]


def test_demo_principal_can_read(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_MODE", "demo")
    monkeypatch.delenv("API_KEYS", raising=False)
    init_db()
    r = TestClient(create_app()).get("/v1/pairs")
    assert r.status_code == 200, r.text
    assert "operados" in r.json()["data"]
