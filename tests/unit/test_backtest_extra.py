"""Extra coverage for backtest/engine.py — exception handling, exit types, drawdown/sharpe edge cases."""
from __future__ import annotations

import pytest

from src.backtest.engine import (
    BacktestEngine,
    BacktestTrade,
    _max_drawdown,
    _sharpe,
)


# ── _max_drawdown ─────────────────────────────────────────────────────────────

def test_max_drawdown_empty_returns_zero():
    assert _max_drawdown([]) == 0.0


def test_max_drawdown_zero_initial_peak_skips_drawdown():
    """Lines 315->313: first equity value is 0 → peak=0 → 'if peak > 0' is False."""
    result = _max_drawdown([0.0, -10.0, -20.0])
    assert result == 0.0


def test_max_drawdown_all_positive_no_drawdown():
    result = _max_drawdown([100.0, 110.0, 120.0])
    assert result == 0.0


def test_max_drawdown_with_trough():
    result = _max_drawdown([100.0, 90.0, 80.0])
    assert result < 0.0


# ── _sharpe ───────────────────────────────────────────────────────────────────

def _trade(pnl: float) -> BacktestTrade:
    return BacktestTrade(
        candle_index=0,
        action="BUY",
        entry_price=50_000.0,
        exit_price=50_000.0 + pnl,
        position_size_pct=2.0,
        pnl_usdt=pnl,
        pnl_pct=pnl / 50_000.0,
        exit_reason="signal",
    )


def test_sharpe_single_trade_returns_none():
    assert _sharpe([_trade(100.0)], 10_000.0) is None


def test_sharpe_zero_variance_returns_none():
    """Line 328: all returns identical → variance=0 → Sharpe is None."""
    trades = [_trade(100.0), _trade(100.0), _trade(100.0)]
    result = _sharpe(trades, 10_000.0)
    assert result is None


def test_sharpe_normal_two_trades():
    trades = [_trade(100.0), _trade(-50.0)]
    result = _sharpe(trades, 10_000.0)
    assert result is not None


# ── BacktestEngine._check_exits ───────────────────────────────────────────────

def test_check_exits_buy_take_profit_hit():
    """Line 186: BUY + high >= tp → returns (tp, 'take_profit')."""
    engine = BacktestEngine()
    trade = {"action": "BUY", "stop_loss": 48_000.0, "take_profit": 52_000.0}
    price, reason = engine._check_exits(trade, high=53_000.0, low=50_000.0, close=53_000.0)
    assert price == 52_000.0
    assert reason == "take_profit"


def test_check_exits_sell_stop_loss_hit():
    """SELL + high >= sl → returns (sl, 'stop_loss')."""
    engine = BacktestEngine()
    trade = {"action": "SELL", "stop_loss": 52_000.0, "take_profit": 48_000.0}
    price, reason = engine._check_exits(trade, high=53_000.0, low=50_000.0, close=53_000.0)
    assert price == 52_000.0
    assert reason == "stop_loss"


def test_check_exits_sell_take_profit_hit():
    """SELL + low <= tp → returns (tp, 'take_profit')."""
    engine = BacktestEngine()
    trade = {"action": "SELL", "stop_loss": 53_000.0, "take_profit": 48_000.0}
    price, reason = engine._check_exits(trade, high=51_000.0, low=47_000.0, close=47_000.0)
    assert price == 48_000.0
    assert reason == "take_profit"


def test_check_exits_sell_no_exit():
    """Lines 187->193: SELL + no exit triggered → returns (None, '')."""
    engine = BacktestEngine()
    trade = {"action": "SELL", "stop_loss": 55_000.0, "take_profit": 45_000.0}
    # high < sl (53k < 55k) and low > tp (50k > 45k) → no exit
    price, reason = engine._check_exits(trade, high=53_000.0, low=50_000.0, close=52_000.0)
    assert price is None
    assert reason == ""


def test_check_exits_no_sl_no_tp():
    """No stop/tp → returns (None, '')."""
    engine = BacktestEngine()
    trade = {"action": "BUY", "stop_loss": None, "take_profit": None}
    price, reason = engine._check_exits(trade, high=53_000.0, low=50_000.0, close=52_000.0)
    assert price is None


# ── BacktestEngine.run — strategy exception path ──────────────────────────────

@pytest.mark.asyncio
async def test_run_strategy_exception_continues(tmp_path):
    """Lines 130-132: strategy.analyze raises → logged and candle skipped."""

    class FailingStrategy:
        async def analyze(self, market_data):
            raise RuntimeError("strategy crashed")

    engine = BacktestEngine(initial_capital=10_000.0)
    ts = 1_700_000_000_000
    ohlcv = [
        [ts + i * 3600_000, 50_000.0, 50_500.0, 49_500.0, 50_000.0, 100.0]
        for i in range(30)
    ]
    result = await engine.run(FailingStrategy(), ohlcv)
    # Should complete without crash (all candles skipped due to exception)
    assert result.total_trades == 0
