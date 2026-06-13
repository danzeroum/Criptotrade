"""Extra coverage for GridTradingStrategy — hold conditions and confidence."""
from __future__ import annotations

import pytest

from src.strategies.grid_trading import GridTradingStrategy


def _market_data(**kw):
    base = {
        "current_price": 50_000.0,
        "regime": "sideways",
        "indicators": None,
        "volume_profile": None,
        "symbol": "BTC/USDT",
    }
    base.update(kw)
    return base


@pytest.mark.asyncio
async def test_hold_when_price_is_zero():
    """Line 48: current_price=0 → HOLD returned immediately."""
    strategy = GridTradingStrategy()
    result = await strategy.analyze(_market_data(current_price=0.0))
    assert result["action"] == "hold"
    assert "unavailable" in result["reason"]


@pytest.mark.asyncio
async def test_hold_when_regime_not_sideways():
    """Line 52: regime=trending → HOLD with reason."""
    strategy = GridTradingStrategy()
    result = await strategy.analyze(_market_data(regime="trending"))
    assert result["action"] == "hold"
    assert "trending" in result["reason"]


@pytest.mark.asyncio
async def test_hold_when_ema_spread_too_wide():
    """Line 61: EMA spread > 2% → HOLD."""
    from src.analysis.indicators import TechnicalIndicators

    ind = TechnicalIndicators(
        current_price=50_000.0,
        ema_fast=52_000.0, ema_slow=50_000.0,  # spread = 4%
        sma_20=None, sma_50=None, sma_200=None,
        rsi=None, stochastic_k=None, stochastic_d=None,
        macd_line=None, macd_signal=None, macd_hist=None,
        bb_upper=None, bb_middle=None, bb_lower=None,
        bb_percent=None, atr=None, volume_ratio=None, obv=None,
    )
    strategy = GridTradingStrategy()
    result = await strategy.analyze(_market_data(indicators=ind))
    assert result["action"] == "hold"
    assert "EMA spread" in result["reason"]


@pytest.mark.asyncio
async def test_grid_entry_long_when_no_vp():
    """Default direction=long when no volume_profile.poc."""
    strategy = GridTradingStrategy()
    result = await strategy.analyze(_market_data())
    assert result["action"] == "buy"
    assert result["direction"] == "long"


@pytest.mark.asyncio
async def test_grid_entry_short_when_price_above_poc():
    """direction=short when current_price > vp.poc."""
    from unittest.mock import MagicMock
    vp = MagicMock()
    vp.poc = 40_000.0
    strategy = GridTradingStrategy()
    result = await strategy.analyze(_market_data(volume_profile=vp))
    assert result["direction"] == "short"
    assert result["action"] == "sell"


# ── _confidence branches ──────────────────────────────────────────────────────

def test_confidence_vol_between_1_and_2_pct():
    """Lines 125-126: 0.01 <= atr/bb_middle < 0.02 → +0.10."""
    from src.analysis.indicators import TechnicalIndicators

    ind = TechnicalIndicators(
        current_price=50_000.0, atr=750.0, bb_middle=50_000.0,  # vol = 1.5%
        volume_ratio=0.5,  # outside 0.7-1.5 → no volume bonus
        sma_20=None, sma_50=None, sma_200=None,
        ema_fast=None, ema_slow=None,
        rsi=None, stochastic_k=None, stochastic_d=None,
        macd_line=None, macd_signal=None, macd_hist=None,
        bb_upper=None, bb_lower=None, bb_percent=None, obv=None,
    )
    score = GridTradingStrategy._confidence(ind)
    assert score == pytest.approx(0.60)  # 0.50 + 0.10


def test_confidence_vol_below_1_pct():
    """Lines 123-124: atr/bb_middle < 0.01 → +0.20."""
    from src.analysis.indicators import TechnicalIndicators

    ind = TechnicalIndicators(
        current_price=50_000.0, atr=100.0, bb_middle=50_000.0,  # vol = 0.2%
        volume_ratio=0.5,  # no volume bonus
        sma_20=None, sma_50=None, sma_200=None,
        ema_fast=None, ema_slow=None,
        rsi=None, stochastic_k=None, stochastic_d=None,
        macd_line=None, macd_signal=None, macd_hist=None,
        bb_upper=None, bb_lower=None, bb_percent=None, obv=None,
    )
    score = GridTradingStrategy._confidence(ind)
    assert score == pytest.approx(0.70)  # 0.50 + 0.20


def test_confidence_stable_volume():
    """Lines 128-129: volume_ratio 0.7-1.5 → +0.15."""
    from src.analysis.indicators import TechnicalIndicators

    ind = TechnicalIndicators(
        current_price=50_000.0, atr=None, bb_middle=None,  # skip vol calc
        volume_ratio=1.0,  # 0.7 < 1.0 < 1.5 → +0.15
        sma_20=None, sma_50=None, sma_200=None,
        ema_fast=None, ema_slow=None,
        rsi=None, stochastic_k=None, stochastic_d=None,
        macd_line=None, macd_signal=None, macd_hist=None,
        bb_upper=None, bb_lower=None, bb_percent=None, obv=None,
    )
    score = GridTradingStrategy._confidence(ind)
    assert score == pytest.approx(0.65)  # 0.50 + 0.15


def test_confidence_no_indicators():
    """No indicators → base score 0.50."""
    score = GridTradingStrategy._confidence(None)
    assert score == pytest.approx(0.50)


def test_get_parameters_returns_dict():
    """Line 137: get_parameters returns expected keys."""
    strategy = GridTradingStrategy(grid_levels=5, grid_spacing_pct=0.5)
    params = strategy.get_parameters()
    assert params["name"] == "Grid Trading"
    assert params["grid_levels"] == 5
