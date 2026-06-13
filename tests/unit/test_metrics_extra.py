"""Extra coverage for core/metrics.py — _parse_ts, _sharpe, _max_drawdown edge cases."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import List

import pytest

from src.core.ledger import TradingLedger
from src.core.metrics import PortfolioMetricsCalculator


@pytest.fixture
def calc(tmp_path):
    ledger = TradingLedger(tmp_path / "m.jsonl")
    return PortfolioMetricsCalculator(ledger, initial_capital=10_000.0)


def _closed(ledger: TradingLedger, pnl: float, oid: str, ts: str) -> None:
    ledger.log_decision("position_closed", {"order_id": oid, "pnl": pnl}, timestamp=ts)


# ── _parse_ts ─────────────────────────────────────────────────────────────────

def test_parse_ts_none_returns_none():
    """Line 72: _parse_ts(None) → returns None."""
    from src.core.metrics import _parse_ts

    assert _parse_ts(None) is None


def test_parse_ts_empty_string_returns_none():
    """Line 72: _parse_ts("") → returns None."""
    from src.core.metrics import _parse_ts

    assert _parse_ts("") is None


def test_parse_ts_invalid_returns_none():
    """Lines 75-76: ValueError path → returns None."""
    from src.core.metrics import _parse_ts

    assert _parse_ts("not-a-date") is None


def test_parse_ts_valid_z_suffix():
    """_parse_ts handles trailing Z by replacing with +00:00."""
    from src.core.metrics import _parse_ts

    result = _parse_ts("2024-01-15T12:00:00Z")
    assert result is not None
    assert result.year == 2024


# ── _max_drawdown with zero initial capital ───────────────────────────────────

def test_max_drawdown_zero_initial_capital_peak_zero(tmp_path):
    """Line 178->175: peak=0 when initial_capital=0 → skip drawdown calc."""
    ledger = TradingLedger(tmp_path / "ld.jsonl")
    calc = PortfolioMetricsCalculator(ledger, initial_capital=0.0)
    ts = datetime.now(UTC).isoformat()
    _closed(ledger, -100.0, "ord1", ts)
    metrics = calc.compute()
    # Should not crash; max_drawdown defaults to 0.0 when peak = 0
    assert isinstance(metrics.max_drawdown, float)


# ── _sharpe edge cases ────────────────────────────────────────────────────────

def test_sharpe_single_unique_day_returns_none(tmp_path):
    """Line 207: only 1 distinct trading day → Sharpe is None."""
    ledger = TradingLedger(tmp_path / "ld.jsonl")
    calc = PortfolioMetricsCalculator(ledger, initial_capital=10_000.0)
    ts = "2024-01-10T10:00:00+00:00"
    _closed(ledger, 100.0, "o1", ts)
    _closed(ledger, 200.0, "o2", ts)  # same day as o1
    metrics = calc.compute()
    assert metrics.sharpe_ratio is None


def test_sharpe_zero_stdev_returns_none(tmp_path):
    """Line 218: all daily returns are 0.0 → stdev=0 → Sharpe is None."""
    ledger = TradingLedger(tmp_path / "ld.jsonl")
    calc = PortfolioMetricsCalculator(ledger, initial_capital=10_000.0)
    # Zero PnL on two different days → returns [0.0, 0.0] → stdev=0
    _closed(ledger, 0.0, "o1", "2024-01-10T10:00:00+00:00")
    _closed(ledger, 0.0, "o2", "2024-01-11T10:00:00+00:00")
    metrics = calc.compute()
    assert metrics.sharpe_ratio is None


def test_sharpe_negative_equity_returns_none(tmp_path):
    """Line 212: equity hits zero/negative during Sharpe computation → returns None."""
    ledger = TradingLedger(tmp_path / "ld.jsonl")
    calc = PortfolioMetricsCalculator(ledger, initial_capital=100.0)
    # Massive loss on day 1, then gain on day 2
    _closed(ledger, -200.0, "o1", "2024-01-10T10:00:00+00:00")
    _closed(ledger, 50.0, "o2", "2024-01-11T10:00:00+00:00")
    metrics = calc.compute()
    # After -200 from 100 initial, equity becomes -100 → should return None
    assert metrics.sharpe_ratio is None
