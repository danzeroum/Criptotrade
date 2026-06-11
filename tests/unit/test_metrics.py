"""Unit tests for the portfolio metrics engine and enriched ledger."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from src.core.ledger import TradingLedger
from src.core.metrics import PortfolioMetricsCalculator


@pytest.fixture
def ledger(tmp_path) -> TradingLedger:
    return TradingLedger(tmp_path / "trades.jsonl")


def _append(led: TradingLedger, event_type: str, data: dict, ts: datetime) -> None:
    """Append an entry with an explicit timestamp (bypasses 'now')."""
    entry = {"timestamp": ts.isoformat(), "event_type": event_type, "data": data}
    with led.ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


# ----------------------------------------------------------------- ledger API
def test_log_fill_records_notional(ledger):
    ledger.log_fill("ord_1", "BTC/USDT", "BUY", price=100.0, quantity=2.0, fee=0.5)
    fills = ledger.get_events("order_fill")
    assert len(fills) == 1
    data = fills[0]["data"]
    assert data["side"] == "buy"  # normalised
    assert data["notional"] == 200.0
    assert data["fee"] == 0.5


def test_log_position_closed_long_pnl(ledger):
    # Long: bought at 100, sold at 110, qty 2 -> gross 20, net 19 after fee 1.
    ledger.log_position_closed("ord_1", "BTC/USDT", "buy", 100.0, 110.0, 2.0, fee=1.0)
    closed = ledger.get_events("position_closed")[0]["data"]
    assert closed["gross_pnl"] == 20.0
    assert closed["pnl"] == 19.0
    assert closed["pnl_pct"] == pytest.approx(19.0 / 200.0)


def test_log_position_closed_short_pnl(ledger):
    # Short: sold at 100, covered at 90, qty 1 -> gross 10.
    ledger.log_position_closed("ord_2", "ETH/USDT", "sell", 100.0, 90.0, 1.0)
    closed = ledger.get_events("position_closed")[0]["data"]
    assert closed["gross_pnl"] == 10.0
    assert closed["pnl"] == 10.0


def test_read_all_missing_file_returns_empty(tmp_path):
    led = TradingLedger(tmp_path / "does_not_exist" / "trades.jsonl")
    # Parent is created on init, but file does not exist until first write.
    led.ledger_path.unlink(missing_ok=True)
    assert led.read_all() == []


# ---------------------------------------------------------------- metrics
def test_empty_ledger_degrades_gracefully(ledger):
    metrics = PortfolioMetricsCalculator(ledger, initial_capital=10_000.0).compute()
    assert metrics.has_data is False
    assert metrics.total_trades == 0
    assert metrics.sharpe_ratio is None
    assert metrics.win_rate is None
    assert metrics.profit_factor is None
    assert metrics.max_drawdown == 0.0
    assert metrics.portfolio_value_usdt == 10_000.0


def test_win_rate_and_pnl(ledger):
    base = datetime(2026, 1, 1, tzinfo=UTC)
    _append(ledger, "position_closed",
            {"order_id": "a", "pnl": 100.0}, base)
    _append(ledger, "position_closed",
            {"order_id": "b", "pnl": -50.0}, base + timedelta(days=1))
    _append(ledger, "position_closed",
            {"order_id": "c", "pnl": 200.0}, base + timedelta(days=2))

    m = PortfolioMetricsCalculator(ledger, 10_000.0).compute(now=base + timedelta(days=3))
    assert m.total_trades == 3
    assert m.win_rate == pytest.approx(2 / 3)
    assert m.pnl_period_usdt == 250.0
    assert m.portfolio_value_usdt == 10_250.0
    assert m.profit_factor == pytest.approx(300.0 / 50.0)


def test_max_drawdown(ledger):
    base = datetime(2026, 1, 1, tzinfo=UTC)
    # Equity: 10000 -> 11000 (peak) -> 9000 -> 9500.
    for i, pnl in enumerate([1000.0, -2000.0, 500.0]):
        _append(ledger, "position_closed", {"order_id": str(i), "pnl": pnl},
                base + timedelta(days=i))
    m = PortfolioMetricsCalculator(ledger, 10_000.0).compute(now=base + timedelta(days=4))
    # Drawdown from peak 11000 to trough 9000 = -2000/11000.
    assert m.max_drawdown == pytest.approx(-2000.0 / 11000.0, rel=1e-4)


def test_sharpe_needs_two_days(ledger):
    base = datetime(2026, 1, 1, tzinfo=UTC)
    # Two trades, same day -> only one daily return -> Sharpe undefined.
    _append(ledger, "position_closed", {"order_id": "a", "pnl": 10.0}, base)
    _append(ledger, "position_closed", {"order_id": "b", "pnl": 20.0}, base)
    m = PortfolioMetricsCalculator(ledger, 10_000.0).compute(now=base + timedelta(days=1))
    assert m.sharpe_ratio is None


def test_sharpe_positive_for_consistent_gains(ledger):
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(5):
        _append(ledger, "position_closed", {"order_id": str(i), "pnl": 100.0},
                base + timedelta(days=i))
    m = PortfolioMetricsCalculator(ledger, 10_000.0).compute(now=base + timedelta(days=6))
    # Steadily positive but slightly varying returns -> finite positive Sharpe.
    assert m.sharpe_ratio is not None
    assert m.sharpe_ratio > 0


def test_open_position_drives_exposure(ledger):
    ledger.log_fill("ord_open", "BTC/USDT", "buy", price=100.0, quantity=20.0)  # notional 2000
    m = PortfolioMetricsCalculator(ledger, 10_000.0).compute()
    assert m.open_positions == 1
    assert m.exposure_pct == pytest.approx(2000.0 / 10_000.0)
    assert m.has_data is True


def test_closed_fill_not_counted_as_open(ledger):
    ledger.log_fill("ord_x", "BTC/USDT", "buy", price=100.0, quantity=1.0)
    ledger.log_position_closed("ord_x", "BTC/USDT", "buy", 100.0, 110.0, 1.0)
    m = PortfolioMetricsCalculator(ledger, 10_000.0).compute()
    assert m.open_positions == 0


def test_period_filter_scopes_pnl(ledger):
    now = datetime(2026, 6, 1, tzinfo=UTC)
    _append(ledger, "position_closed", {"order_id": "old", "pnl": 500.0},
            now - timedelta(days=40))
    _append(ledger, "position_closed", {"order_id": "recent", "pnl": 100.0},
            now - timedelta(days=2))
    m = PortfolioMetricsCalculator(ledger, 10_000.0).compute(period="7d", now=now)
    assert m.total_trades == 1
    assert m.pnl_period_usdt == 100.0
    # Portfolio value still reflects ALL realised P&L (500 + 100).
    assert m.portfolio_value_usdt == 10_600.0


def test_invalid_period_raises(ledger):
    with pytest.raises(ValueError):
        PortfolioMetricsCalculator(ledger).compute(period="bogus")
