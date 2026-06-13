"""Per-symbol filter on /v1/metrics and /v1/metrics/equity."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.core.ledger import TradingLedger
from src.core.metrics import PortfolioMetricsCalculator


@pytest.fixture
def client(tmp_path):
    # Inject a seeded ledger directly (no reliance on LEDGER_DIR env timing,
    # which is fragile under full-suite ordering).
    led = TradingLedger(tmp_path / "trades.jsonl")
    led.log_position_closed("b1", "BTC/USDT", "buy", 100.0, 110.0, 1.0)  # +10
    led.log_position_closed("e1", "ETH/USDT", "buy", 100.0, 90.0, 1.0)   # -10
    app = create_app()
    app.dependency_overrides[deps.get_ledger] = lambda: led
    app.dependency_overrides[deps.get_metrics_calculator] = (
        lambda: PortfolioMetricsCalculator(led, initial_capital=10_000.0)
    )
    return TestClient(app)


def test_metrics_symbol_filter_scopes_trades(client):
    btc = client.get("/v1/metrics?period=all&symbol=BTC/USDT").json()["data"]
    assert btc["total_trades"] == 1
    both = client.get("/v1/metrics?period=all").json()["data"]
    assert both["total_trades"] == 2


def test_metrics_symbol_in_self_link(client):
    body = client.get("/v1/metrics?period=all&symbol=BTC/USDT").json()
    assert "symbol=BTC/USDT" in body["_links"]["self"]  # HATEOAS alias


def test_metrics_invalid_symbol_returns_422(client):
    r = client.get("/v1/metrics?symbol=FOO/BAR")
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_pair"  # handler unwraps the detail


def test_equity_symbol_filter_differs_per_pair(client):
    btc = client.get("/v1/metrics/equity?period=all&symbol=BTC/USDT").json()["data"]
    eth = client.get("/v1/metrics/equity?period=all&symbol=ETH/USDT").json()["data"]
    assert btc[-1]["equity"] != eth[-1]["equity"]  # +10 profit vs -10 loss
