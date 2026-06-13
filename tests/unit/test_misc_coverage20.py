"""Twentieth batch — base_strategy get_parameters, metrics sharpe single-day."""
from __future__ import annotations

import datetime
import pytest
from unittest.mock import patch


# ── base_strategy — get_parameters fallback (line 17) ─────────────────────────

def test_base_strategy_get_parameters_default():
    """Line 17: concrete strategy that does NOT override get_parameters → returns {}."""
    from src.strategies.base_strategy import BaseStrategy

    class _MinimalStrategy(BaseStrategy):
        async def analyze(self, market_data):
            return {}
        # intentionally does NOT override get_parameters

    strategy = _MinimalStrategy()
    params = strategy.get_parameters()
    # Calls BaseStrategy.get_parameters (line 17: return {})
    assert params == {}


# ── metrics — _sharpe with single-day trades (line 212) ───────────────────────

def test_metrics_sharpe_single_day_returns_none(tmp_path):
    """Line 212: all closed trades on same day → len(returns) == 1 < 2 → return None."""
    from src.core.ledger import TradingLedger
    from src.core.metrics import PortfolioMetricsCalculator

    ledger = TradingLedger(tmp_path / "m.jsonl")
    calc = PortfolioMetricsCalculator(ledger, initial_capital=10_000.0)

    today = datetime.datetime.now(datetime.timezone.utc)
    # Both trades on the same day → only 1 unique day → len(returns) == 1 < 2 → return None
    closed = [
        {"pnl": 100.0, "_ts": today},
        {"pnl":  50.0, "_ts": today},   # same day as first
    ]
    result = calc._sharpe(closed)
    assert result is None   # line 212 covered
