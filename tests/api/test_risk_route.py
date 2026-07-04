"""Regression tests for /v1/risk — yaml path resolution and daily-loss reading."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.api.routes.risk import _RISK_PARAMS_PATH, _daily_loss_pct
from src.core.ledger import TradingLedger
from src.core.metrics import PortfolioMetricsCalculator


def test_risk_params_path_points_to_real_file():
    # Regression: parents[4] resolved outside the repo, silently loading {} on
    # GET and 500ing on PATCH. The path must resolve to the tracked yaml.
    assert _RISK_PARAMS_PATH.exists(), _RISK_PARAMS_PATH
    assert _RISK_PARAMS_PATH.name == "risk_params.yaml"


def test_daily_loss_reads_entry_level_timestamp(tmp_path):
    # Regression: the close time is the entry-level ledger timestamp — the data
    # payload has no "timestamp" key, so the old code always summed 0.
    ledger = TradingLedger(tmp_path / "trades.jsonl")
    ledger.log_position_closed(
        order_id="ord_1", symbol="BTC/USDT", side="buy",
        entry_price=50_000.0, exit_price=49_000.0, quantity=0.1,  # pnl -100
    )
    assert _daily_loss_pct(ledger, initial_capital=10_000.0) == pytest.approx(-1.0)


@pytest.fixture
def client(tmp_path):
    ledger = TradingLedger(tmp_path / "trades.jsonl")
    app = create_app()
    app.dependency_overrides[deps.get_ledger] = lambda: ledger
    app.dependency_overrides[deps.get_metrics_calculator] = lambda: PortfolioMetricsCalculator(
        ledger, 10_000.0
    )
    test_client = TestClient(app)
    test_client.ledger = ledger  # type: ignore[attr-defined]
    return test_client


def test_risk_config_returns_yaml_values(client):
    # With the fixed path, values come from config/strategies/risk_params.yaml
    # (not the code-side fallbacks — the yaml is the operator's contract).
    body = client.get("/v1/risk/config").json()["data"]
    assert body["max_daily_loss_pct"] == 5.0
    assert body["max_weekly_loss_pct"] == 10.0
    assert body["max_monthly_loss_pct"] == 15.0


def test_circuit_breaker_endpoint_sees_todays_loss(client):
    # A -5% day must surface as a trigger (limit is 4%).
    client.ledger.log_position_closed(
        order_id="ord_cb", symbol="BTC/USDT", side="buy",
        entry_price=50_000.0, exit_price=45_000.0, quantity=1.0,  # pnl -5000 = -50%
    )
    body = client.get("/v1/risk/circuit-breaker").json()["data"]
    assert body["status"] == "triggered"
    assert body["triggers"]
