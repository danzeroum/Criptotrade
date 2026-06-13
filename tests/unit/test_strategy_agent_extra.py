"""Extra coverage for StrategyAgent — confidence branches and signal paths."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.strategy_agent import StrategyAgent
from src.analysis.indicators import TechnicalIndicators
from src.analysis.support_resistance import SRLevels


# ── helpers ──────────────────────────────────────────────────────────────────

def _ind(**kwargs) -> TechnicalIndicators:
    defaults = dict(
        current_price=50_000.0,
        sma_20=50_100.0, sma_50=50_050.0, sma_200=50_000.0,
        ema_fast=50_050.0, ema_slow=50_025.0,
        rsi=50.0, stochastic_k=50.0, stochastic_d=50.0,
        macd_line=0.0, macd_signal=0.0, macd_hist=0.0,
        bb_upper=51_000.0, bb_middle=50_000.0, bb_lower=49_000.0,
        bb_percent=0.5, atr=100.0, volume_ratio=1.0, obv=0.0,
    )
    defaults.update(kwargs)
    return TechnicalIndicators(**defaults)


def _analysis(action="BUY", *, ind=None, trend="bullish", sr=None, rsi_div=None, macd_div=None) -> dict:
    return {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "current_price": 50_000.0,
        "trend": trend,
        "regime": "trending",
        "eligible_strategies": ["dca"],
        "indicators": ind or _ind(),
        "support_resistance": sr,
        "fibonacci_levels": {},
        "volume_profile": None,
        "rsi_divergence": rsi_div,
        "macd_divergence": macd_div,
        "market_extreme": None,
        "_ohlcv": [],
    }


def _signal(action="BUY", entry_price=50_000.0, **kw) -> dict:
    return {
        "action": action,
        "entry_price": entry_price,
        "stop_loss": None,
        "take_profit": None,
        "position_size_pct": 2.0,
        **kw,
    }


# ── _calculate_confidence ─────────────────────────────────────────────────────

def test_confidence_no_indicators_returns_half():
    agent = StrategyAgent()
    analysis = _analysis()
    analysis["indicators"] = None
    conf = agent._calculate_confidence(analysis, _signal())
    assert conf == 0.5


def test_confidence_buy_bullish_trend_full_credit():
    """BUY + bullish → trend_alignment += 0.25."""
    agent = StrategyAgent()
    conf = agent._calculate_confidence(
        _analysis(action="BUY", trend="bullish"),
        _signal(action="BUY"),
    )
    assert conf > 0.25


def test_confidence_sell_bearish_trend():
    agent = StrategyAgent()
    conf = agent._calculate_confidence(
        _analysis(action="SELL", trend="bearish"),
        _signal(action="SELL"),
    )
    assert conf > 0.25


def test_confidence_hold_partial_credit():
    agent = StrategyAgent()
    conf = agent._calculate_confidence(
        _analysis(action="HOLD", trend="bullish"),
        _signal(action="HOLD"),
    )
    assert conf >= 0.10


def test_confidence_rsi_buy_zone():
    """RSI < 55 + BUY → indicator_hits += 1."""
    agent = StrategyAgent()
    ind = _ind(rsi=40.0, macd_hist=0.0, bb_percent=None)
    conf = agent._calculate_confidence(_analysis(action="BUY", ind=ind), _signal(action="BUY"))
    assert conf > 0.10


def test_confidence_rsi_sell_zone():
    """RSI > 45 + SELL → indicator_hits += 1."""
    agent = StrategyAgent()
    ind = _ind(rsi=60.0, macd_hist=0.0, bb_percent=None)
    conf = agent._calculate_confidence(_analysis(action="SELL", ind=ind), _signal(action="SELL"))
    assert conf > 0.10


def test_confidence_macd_buy():
    """macd_hist > 0 + BUY → indicator_hits += 1."""
    agent = StrategyAgent()
    ind = _ind(rsi=None, macd_hist=5.0, bb_percent=None)
    conf = agent._calculate_confidence(_analysis(action="BUY", ind=ind), _signal(action="BUY"))
    assert conf > 0.10


def test_confidence_macd_sell():
    """macd_hist < 0 + SELL → indicator_hits += 1."""
    agent = StrategyAgent()
    ind = _ind(rsi=None, macd_hist=-5.0, bb_percent=None)
    conf = agent._calculate_confidence(_analysis(action="SELL", ind=ind), _signal(action="SELL"))
    assert conf > 0.10


def test_confidence_bb_buy_zone():
    """bb_percent < 0.3 + BUY → indicator_hits += 1."""
    agent = StrategyAgent()
    ind = _ind(rsi=None, macd_hist=None, bb_percent=0.1)
    conf = agent._calculate_confidence(_analysis(action="BUY", ind=ind), _signal(action="BUY"))
    assert conf > 0.10


def test_confidence_bb_sell_zone():
    """bb_percent > 0.7 + SELL → indicator_hits += 1."""
    agent = StrategyAgent()
    ind = _ind(rsi=None, macd_hist=None, bb_percent=0.9)
    conf = agent._calculate_confidence(_analysis(action="SELL", ind=ind), _signal(action="SELL"))
    assert conf > 0.10


def test_confidence_sr_proximity_buy():
    """BUY near support → proximity score added."""
    from src.analysis.support_resistance import SRLevels
    agent = StrategyAgent()
    sr = SRLevels(support=49_000.0, resistance=51_000.0)
    conf = agent._calculate_confidence(
        _analysis(action="BUY", sr=sr),
        _signal(action="BUY", entry_price=49_100.0),
    )
    assert conf > 0.10


def test_confidence_sr_proximity_sell():
    """SELL near resistance → proximity score added."""
    from src.analysis.support_resistance import SRLevels
    agent = StrategyAgent()
    sr = SRLevels(support=48_000.0, resistance=52_000.0)
    conf = agent._calculate_confidence(
        _analysis(action="SELL", sr=sr),
        _signal(action="SELL", entry_price=51_500.0),
    )
    assert conf > 0.10


def test_confidence_volume_strong():
    """volume_ratio > 1.2 → += 0.15."""
    agent = StrategyAgent()
    ind = _ind(volume_ratio=2.0)
    conf = agent._calculate_confidence(_analysis(ind=ind), _signal())
    assert conf >= 0.10


def test_confidence_volume_moderate():
    """0.8 < volume_ratio ≤ 1.2 → += 0.07."""
    agent = StrategyAgent()
    ind = _ind(volume_ratio=1.0)
    conf = agent._calculate_confidence(_analysis(ind=ind), _signal())
    assert conf >= 0.10


def test_confidence_rsi_divergence_buy_bonus():
    """Bullish RSI divergence + BUY → += 0.10."""
    from src.analysis.indicators import DivergenceResult
    agent = StrategyAgent()
    div = DivergenceResult(detected=True, kind="bullish_divergence", description="rsi bull")
    conf = agent._calculate_confidence(
        _analysis(action="BUY", rsi_div=div),
        _signal(action="BUY"),
    )
    assert conf > 0.10


def test_confidence_rsi_divergence_sell_bonus():
    """Bearish RSI divergence + SELL → += 0.10."""
    from src.analysis.indicators import DivergenceResult
    agent = StrategyAgent()
    div = DivergenceResult(detected=True, kind="bearish_divergence", description="rsi bear")
    conf = agent._calculate_confidence(
        _analysis(action="SELL", rsi_div=div),
        _signal(action="SELL"),
    )
    assert conf > 0.10


def test_confidence_macd_divergence_buy_bonus():
    """Bullish MACD divergence (no RSI div) + BUY → += 0.05."""
    from src.analysis.indicators import DivergenceResult
    agent = StrategyAgent()
    macd_div = DivergenceResult(detected=True, kind="bullish_divergence", description="macd bull")
    conf = agent._calculate_confidence(
        _analysis(action="BUY", macd_div=macd_div),
        _signal(action="BUY"),
    )
    assert conf > 0.10


def test_confidence_macd_divergence_sell_bonus():
    """Bearish MACD divergence (no RSI div) + SELL → += 0.05."""
    from src.analysis.indicators import DivergenceResult
    agent = StrategyAgent()
    macd_div = DivergenceResult(detected=True, kind="bearish_divergence", description="macd bear")
    conf = agent._calculate_confidence(
        _analysis(action="SELL", macd_div=macd_div),
        _signal(action="SELL"),
    )
    assert conf > 0.10


# ── _generate_signal ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_signal_no_eligible_strategies():
    """Line 170: no eligible strategies → HOLD with reason."""
    agent = StrategyAgent()
    analysis = _analysis()
    analysis["eligible_strategies"] = []
    analysis["regime"] = "chaotic"
    signal, conf = await agent._generate_signal(analysis)
    assert signal["action"] == "HOLD"
    assert "No strategy eligible" in signal["reason"]
    assert conf is None


@pytest.mark.asyncio
async def test_generate_signal_unknown_strategy_key():
    """Line 175: strategy key not in registry → HOLD with reason."""
    agent = StrategyAgent()
    analysis = _analysis()
    analysis["eligible_strategies"] = ["nonexistent_strategy_xyz"]
    signal, conf = await agent._generate_signal(analysis)
    assert signal["action"] == "HOLD"
    assert "nonexistent_strategy_xyz" in signal["reason"]


# ── execute: validate_input failure ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_invalid_task_raises():
    """Line 38: validate_input returns False → ValueError raised."""
    agent = StrategyAgent()
    with pytest.raises(ValueError, match="Invalid strategy task"):
        await agent.execute(None)  # None fails validate_input


# ── execute: confidence blending ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_confidence_uses_agent_when_strategy_confidence_none():
    """Line 52: strategy_confidence is None → confidence = agent_confidence."""
    agent = StrategyAgent()  # no exchange client → stub analysis
    result = await agent.execute({"symbol": "BTC/USDT", "timeframe": "1h"})
    assert result["success"] is True
    # Stub analysis always returns a result with some confidence
    assert 0.0 < result["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_execute_confidence_blended_when_strategy_returns_confidence():
    """Lines 47-50: strategy_confidence is not None + action != HOLD → blended."""
    agent = StrategyAgent()
    # Override _generate_signal to return non-None confidence
    mock_signal = {"action": "BUY", "entry_price": 50_000.0, "position_size_pct": 2.0,
                   "stop_loss": None, "take_profit": None}

    async def _mock_generate(analysis):
        return mock_signal, 0.85  # strategy_confidence = 0.85

    agent._generate_signal = _mock_generate  # type: ignore[method-assign]
    result = await agent.execute({"symbol": "BTC/USDT"})
    assert result["success"] is True
    # confidence should be a blend: 0.6*0.85 + 0.4*agent_conf
    assert 0.1 <= result["confidence"] <= 0.95


# ── _sanitize_for_log ─────────────────────────────────────────────────────────

def test_sanitize_removes_ohlcv_and_converts_dataclasses():
    """Lines 388-398: _sanitize strips _ohlcv and converts dataclass fields."""
    agent = StrategyAgent()
    ind = _ind()  # TechnicalIndicators is a dataclass
    analysis = _analysis(ind=ind)
    analysis["_ohlcv"] = [[1, 2, 3, 4, 5, 6]] * 10
    sanitized = agent._sanitize_for_log(analysis)
    assert "_ohlcv" not in sanitized
    assert isinstance(sanitized.get("indicators"), dict)


# ── _explain_reasoning ────────────────────────────────────────────────────────

def test_explain_reasoning_with_market_extreme():
    """Line 414-415: market_extreme present → appended to reasoning."""
    agent = StrategyAgent()
    analysis = _analysis()
    analysis["market_extreme"] = "overbought"
    reasoning = agent._explain_reasoning(analysis, _signal())
    assert "overbought" in reasoning


def test_explain_reasoning_without_indicators():
    """No indicators → only regime and action included."""
    agent = StrategyAgent()
    analysis = _analysis()
    analysis["indicators"] = None
    reasoning = agent._explain_reasoning(analysis, _signal())
    assert "Action:" in reasoning
