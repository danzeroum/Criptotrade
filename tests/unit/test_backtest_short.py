"""Coverage for the SHORT (SELL) path of the backtest engine (P3-5).

The audit flagged the SELL branch of ``_check_exits`` / ``_close_trade`` as
untested (``engine.py`` lines 186-191 and 214 — the long/BUY path was covered,
the short/SELL path was not). These tests exercise it both behaviorally, through
``run()``, and directly for deterministic line coverage and P&L-sign assertions.
"""
from __future__ import annotations

import pytest

from src.backtest.engine import WARMUP_CANDLES, BacktestEngine


class _AlwaysSellStrategy:
    """Always open a SHORT: stop above entry, target below entry."""

    async def analyze(self, market_data):
        price = market_data.get("current_price", 50_000)
        return {
            "action": "sell",
            "position_size_pct": 5.0,
            "stop_loss": price * 1.03,    # a short's stop sits ABOVE entry
            "take_profit": price * 0.94,  # a short's target sits BELOW entry
            "confidence": 0.7,
        }


def _flat_then_drop(n_flat: int, base: float = 50_000.0, drop_low: float = 46_000.0) -> list:
    """``n_flat`` flat candles, then a final candle whose low dips to ``drop_low``
    — enough to hit a short's take-profit (``base * 0.94`` = 47_000)."""
    candles = [[i * 3_600_000, base, base * 1.001, base * 0.999, base, 1000.0] for i in range(n_flat)]
    candles.append([n_flat * 3_600_000, base, base * 1.001, drop_low, base * 0.99, 1000.0])
    return candles


@pytest.mark.asyncio
async def test_run_short_take_profit_is_profitable():
    """A short opened at 50k and closed as price falls to its TP must net a gain."""
    engine = BacktestEngine(slippage_bps=0)
    # entry opens at candle WARMUP_CANDLES (50); the final candle dips to the TP.
    ohlcv = _flat_then_drop(WARMUP_CANDLES + 10)
    result = await engine.run(_AlwaysSellStrategy(), ohlcv)

    assert result.total_trades >= 1
    assert result.total_pnl_usdt > 0          # short profits when price drops
    assert result.total_pnl_pct > 0


# --------------------------------------------------------------------------- #
# Direct, deterministic coverage of the SELL branches (engine.py 186-191, 214) #
# --------------------------------------------------------------------------- #

def _sell_trade() -> dict:
    return {
        "candle_index": 10,
        "action": "SELL",
        "entry_price": 50_000.0,
        "position_size_pct": 10.0,
        "stop_loss": 51_000.0,   # above entry
        "take_profit": 47_000.0,  # below entry
        "capital_at_entry": 10_000.0,
    }


def test_check_exits_short_stop_loss():
    # price spikes up: high >= stop_loss → stopped out at the stop
    price, reason = BacktestEngine(slippage_bps=0)._check_exits(
        _sell_trade(), high=51_200.0, low=49_000.0, close=50_500.0
    )
    assert reason == "stop_loss"
    assert price == 51_000.0


def test_check_exits_short_take_profit():
    # price falls: low <= take_profit → target hit
    price, reason = BacktestEngine(slippage_bps=0)._check_exits(
        _sell_trade(), high=50_100.0, low=46_500.0, close=47_000.0
    )
    assert reason == "take_profit"
    assert price == 47_000.0


def test_check_exits_short_no_exit_between_levels():
    # price stays strictly between target and stop → no exit
    price, reason = BacktestEngine(slippage_bps=0)._check_exits(
        _sell_trade(), high=50_500.0, low=49_500.0, close=50_000.0
    )
    assert price is None
    assert reason == ""


def test_close_trade_short_profit_when_price_falls():
    engine = BacktestEngine(slippage_bps=0)
    trade = engine._close_trade(
        _sell_trade(), exit_price=47_000.0, exit_reason="take_profit", capital=10_000.0
    )
    assert trade.action == "SELL"
    assert trade.pnl_usdt > 0                                   # short gains as price falls
    # raw 6% move minus round-trip commission (entry+exit)
    assert trade.pnl_pct == pytest.approx(0.06 - engine.commission_pct * 2, abs=1e-9)


def test_close_trade_short_loss_when_price_rises():
    trade = BacktestEngine(slippage_bps=0)._close_trade(
        _sell_trade(), exit_price=51_000.0, exit_reason="stop_loss", capital=10_000.0
    )
    assert trade.pnl_usdt < 0                                   # short loses as price rises
