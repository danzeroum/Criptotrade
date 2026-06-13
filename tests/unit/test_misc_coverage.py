"""Miscellaneous edge-case coverage for small uncovered branches across the codebase."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.analysis.indicators import TechnicalIndicators


# ── GridTradingStrategy — missing branches ─────────────────────────────────────

def test_grid_confidence_high_vol_no_elif_bonus():
    """Lines 125->128: vol_pct >= 0.02 → neither < 0.01 nor < 0.02 bonus."""
    from src.strategies.grid_trading import GridTradingStrategy

    ind = TechnicalIndicators(
        current_price=50_000.0,
        atr=2_000.0, bb_middle=50_000.0,  # vol_pct = 0.04 → no vol bonus
        volume_ratio=0.5,
        sma_20=None, sma_50=None, sma_200=None,
        ema_fast=None, ema_slow=None,
        rsi=None, stochastic_k=None, stochastic_d=None,
        macd_line=None, macd_signal=None, macd_hist=None,
        bb_upper=None, bb_lower=None, bb_percent=None, obv=None,
    )
    score = GridTradingStrategy._confidence(ind)
    assert score == pytest.approx(0.50)  # no bonus at all


@pytest.mark.asyncio
async def test_grid_ema_both_none_continues_to_vp():
    """Lines 58->64: ema_fast or ema_slow is None → if ema block skipped."""
    from src.strategies.grid_trading import GridTradingStrategy

    ind = TechnicalIndicators(
        current_price=50_000.0,
        ema_fast=None, ema_slow=None,  # both None → if ema_fast and ema_slow: is False
        sma_20=None, sma_50=None, sma_200=None,
        rsi=None, stochastic_k=None, stochastic_d=None,
        macd_line=None, macd_signal=None, macd_hist=None,
        bb_upper=None, bb_lower=None, bb_percent=None,
        atr=None, volume_ratio=None, obv=None,
    )
    strategy = GridTradingStrategy()
    result = await strategy.analyze({
        "current_price": 50_000.0,
        "regime": "sideways",
        "indicators": ind,
        "volume_profile": None,
    })
    # No hold due to EMA spread (block skipped), proceeds to buy
    assert result["action"] == "buy"


# ── MeanReversionStrategy — missing branch ────────────────────────────────────

def test_mr_confidence_no_indicators():
    """Lines 134->141: indicators=None → if indicators block skipped → base score."""
    from src.strategies.mean_reversion import MeanReversionStrategy

    strat = MeanReversionStrategy()
    score = strat._confidence(rsi=20.0, direction="long", indicators=None)
    # No volume or stochastic bonus → base 0.60 + RSI overshoot only
    assert score >= 0.60


def test_mr_confidence_short_with_high_stoch():
    """Lines 138-139: direction=short and k > 80 → stochastic bonus added."""
    from src.strategies.mean_reversion import MeanReversionStrategy

    ind = TechnicalIndicators(
        current_price=50_000.0,
        stochastic_k=85.0,  # k > 80 → short stoch bonus
        rsi=None, stochastic_d=None,
        sma_20=None, sma_50=None, sma_200=None,
        ema_fast=None, ema_slow=None,
        macd_line=None, macd_signal=None, macd_hist=None,
        bb_upper=None, bb_lower=None, bb_percent=None, bb_middle=None,
        atr=None, volume_ratio=None, obv=None,
    )
    strat = MeanReversionStrategy()
    score = strat._confidence(rsi=80.0, direction="short", indicators=ind)
    # base 0.60 + rsi_overshoot (80-70)/30 * 0.20 ≈ 0.067 + stoch 0.10
    assert score > 0.60


# ── DeveloperAgent — line 90 ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_developer_execute_action_debug():
    """Line 90: tool=debug → returns debugging response."""
    from src.agents.developer_agent import DeveloperAgent

    agent = DeveloperAgent()
    result = await agent.execute_action({"tool": "debug"}, "authenticate users")
    assert "Debugging" in result or "debug" in result.lower()


# ── GuardrailSystem — check_risk_reward risk=0 ────────────────────────────────

def test_check_risk_reward_zero_risk_returns_ok():
    """Lines 94->99: entry == stop → risk=0 → 'if risk > 0' is False → returns (True, '')."""
    from src.safety.guardrails import GuardrailSystem

    gs = GuardrailSystem()
    order = {"entry_price": 100.0, "stop_loss": 100.0, "take_profit": 150.0}
    ok, msg = gs.check_risk_reward(order)
    assert ok is True
    assert msg == ""


# ── DCAOptimizedStrategy — _explain_reasoning lines 162-164 ──────────────────

def test_dca_explain_reasoning_appends_volume_and_dca():
    """Lines 162-164: _explain_reasoning always appends volume and DCA lines."""
    from src.strategies.dca_optimized import DCAOptimizedStrategy

    strat = DCAOptimizedStrategy()
    result = strat._explain_reasoning(
        trend="uptrend",
        indicators={"rsi_oversold": True, "macd_bullish": False},
        volume_ok=True,
    )
    assert "Volume adequate: True" in result
    assert "DCA approach" in result


def test_dca_explain_reasoning_no_confirmed_indicators():
    """Line 159->161: no confirmed indicators → confirmed block skipped."""
    from src.strategies.dca_optimized import DCAOptimizedStrategy

    strat = DCAOptimizedStrategy()
    result = strat._explain_reasoning(
        trend="sideways",
        indicators={"rsi_oversold": False, "macd_bullish": False},
        volume_ok=False,
    )
    assert "Confirmed indicators" not in result
    assert "Volume adequate: False" in result


# ── API backtest route — _SimpleStrategy branches ────────────────────────────

@pytest.mark.asyncio
async def test_backtest_simple_strategy_sell():
    """Line 105: rsi > 70 and macd_hist < 0 → SELL signal."""
    from src.api.routes.backtest import _SimpleStrategy

    strat = _SimpleStrategy()
    result = await strat.analyze({
        "indicators": {"rsi": 75.0, "macd_hist": -0.5, "atr": 500.0},
        "current_price": 50_000.0,
    })
    assert result["action"] == "sell"


@pytest.mark.asyncio
async def test_backtest_simple_strategy_hold():
    """Line 111: rsi mid-range → hold signal."""
    from src.api.routes.backtest import _SimpleStrategy

    strat = _SimpleStrategy()
    result = await strat.analyze({
        "indicators": {"rsi": 50.0, "macd_hist": 0.1},
        "current_price": 50_000.0,
    })
    assert result["action"] == "hold"
