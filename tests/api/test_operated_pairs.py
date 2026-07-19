"""N8² — DB-managed operated pairs (DB > env), CRUD, validation, audit.

The operated_pairs table wins over env SYMBOLS when non-empty; adding validates
quote+allowlist; removing works; both emit config_changed (scope pairs) for A4.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.core.db import init_db
from src.core.pairs import operated_pairs
from src.core.pairs_store import OperatedPairStore


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.delenv("AUTH_MODE", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.setenv("EXCHANGE_DRY_RUN", "true")
    monkeypatch.setenv("MARKET_PAIRS", "BTC/USDT,ETH/USDT,SOL/USDT")
    monkeypatch.setenv("SYMBOLS", "BTC/USDT")
    init_db()
    deps.reset_singletons()
    yield deps.get_ledger()
    deps.reset_singletons()


def test_db_wins_over_env(env):
    # Empty table → env SYMBOLS.
    assert operated_pairs() == ["BTC/USDT"]
    # Populate the table → it wins (∩ allowlist).
    OperatedPairStore().add("ETH/USDT")
    OperatedPairStore().add("SOL/USDT")
    assert set(operated_pairs()) == {"ETH/USDT", "SOL/USDT"}


def test_add_validates_and_persists(env):
    c = TestClient(create_app())
    r = c.post("/v1/pairs/operated", json={"symbol": "ETH/USDT"})
    assert r.status_code == 201, r.text
    assert "ETH/USDT" in [o["symbol"] for o in r.json()["data"]["operados"]]
    assert OperatedPairStore().symbols() == ["ETH/USDT"]


def test_add_rejects_non_usdt_and_non_allowlisted(env):
    c = TestClient(create_app())
    assert c.post("/v1/pairs/operated", json={"symbol": "ETH/BTC"}).status_code == 422
    assert c.post("/v1/pairs/operated", json={"symbol": "DOGE/USDT"}).status_code == 422  # not in allowlist


def test_remove_and_404(env):
    OperatedPairStore().add("ETH/USDT")
    c = TestClient(create_app())
    r = c.delete("/v1/pairs/operated/ETH-USDT")
    assert r.status_code == 200, r.text
    assert OperatedPairStore().symbols() == []
    assert c.delete("/v1/pairs/operated/SOL-USDT").status_code == 404


def test_mutations_are_audited_as_config_changed(env):
    ledger = env
    c = TestClient(create_app())
    c.post("/v1/pairs/operated", json={"symbol": "ETH/USDT"})
    events = ledger.get_events("config_changed")
    assert any(e["data"].get("scope") == "pairs" for e in events)
    # And it shows up in the A4 audit feed.
    r = c.get("/v1/audit?action=config_changed")
    assert r.status_code == 200
    assert any(row["entity"] == "pairs" for row in r.json()["data"])
