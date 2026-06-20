"""GET /v1/trades/closed — closed-trade history with per-trade P&L (CT-006)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.core.ledger import TradingLedger


@pytest.fixture
def client(tmp_path):
    led = TradingLedger(tmp_path / "trades.jsonl")
    led.log_position_closed("b1", "BTC/USDT", "buy", 100.0, 110.0, 1.0)   # long +10
    led.log_position_closed("e1", "ETH/USDT", "buy", 100.0, 90.0, 1.0)    # long -10
    led.log_position_closed("b2", "BTC/USDT", "sell", 100.0, 90.0, 1.0)   # short +10
    app = create_app()
    app.dependency_overrides[deps.get_ledger] = lambda: led
    return TestClient(app)


def test_closed_trades_lists_all_most_recent_first(client):
    body = client.get("/v1/trades/closed?limit=50").json()
    assert body["meta"]["total"] == 3
    assert len(body["data"]) == 3
    assert body["data"][0]["order_id"] == "b2"  # most recent first


def test_closed_trades_symbol_filter(client):
    body = client.get("/v1/trades/closed?symbol=BTC/USDT").json()
    assert body["meta"]["total"] == 2
    assert all(t["symbol"] == "BTC/USDT" for t in body["data"])


def test_closed_trades_pagination(client):
    body = client.get("/v1/trades/closed?limit=1&offset=0").json()
    assert len(body["data"]) == 1
    assert body["meta"]["per_page"] == 1
    assert body["meta"]["total"] == 3


def test_closed_trades_exposes_pnl_fields(client):
    body = client.get("/v1/trades/closed?symbol=ETH/USDT").json()
    trade = body["data"][0]
    assert trade["pnl"] == -10.0
    for field in ("pnl_pct", "entry_price", "exit_price", "quantity", "closed_at"):
        assert field in trade


def test_closed_trades_invalid_symbol_returns_422(client):
    r = client.get("/v1/trades/closed?symbol=FOO/BAR")
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_pair"
