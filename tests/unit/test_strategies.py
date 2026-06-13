"""Tests for DCAOptimizedStrategy and MeanReversionStrategy."""
from __future__ import annotations

import pytest

from src.strategies.dca_optimized import DCAOptimizedStrategy
from src.strategies.mean_reversion import MeanReversionStrategy


# ─────────────────────────────────────────────────────────────────────────────
# DCAOptimizedStrategy
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def dca():
    return DCAOptimizedStrategy()


@pytest.fixture
def dca_custom():
    return DCAOptimizedStrategy({
        "position_size_pct": 3.0,
        "num_entries": 2,
        "spacing_pct": 0.5,
        "stop_loss_pct": 2.0,
        "rsi_oversold": 40,
        "min_volume_ratio": 0.5,
    })


def _entry_data(price=50_000.0, rsi=30, macd=1.0, at_lower=True,
                vol=1_000.0, avg_vol=1_000.0, ma20=51_000.0, ma50=52_000.0) -> dict:
    """Market data that satisfies DCA entry conditions."""
    return {
        "symbol": "BTC/USDT",
        "current_price": price,
        "rsi": rsi,
        "macd_histogram": macd,
        "at_bollinger_lower": at_lower,
        "volume_24h": vol,
        "avg_volume": avg_vol,
        "ma_20": ma20,
        "ma_50": ma50,
    }


@pytest.mark.asyncio
async def test_dca_entry_signal_when_conditions_met(dca):
    data = _entry_data()
    result = await dca.analyze(data)
    assert result["action"] == "DCA_ENTRY"
    assert result["confidence"] > 0.5
    sig = result["signal"]
    assert sig["symbol"] == "BTC/USDT"
    assert len(sig["entries"]) == 3
    assert sig["risk_reward_ratio"] == pytest.approx(3.0)


@pytest.mark.asyncio
async def test_dca_waits_when_conditions_not_met(dca):
    data = _entry_data(rsi=60, macd=-1.0, at_lower=False)
    result = await dca.analyze(data)
    assert result["action"] == "WAIT"
    assert result["confidence"] == pytest.approx(0.0)
    assert result["signal"] is None


@pytest.mark.asyncio
async def test_dca_waits_when_volume_insufficient(dca):
    data = _entry_data(vol=100.0, avg_vol=1_000.0)  # ratio = 0.1 < 0.8
    result = await dca.analyze(data)
    assert result["action"] == "WAIT"


@pytest.mark.asyncio
async def test_dca_sideways_trend_path(dca):
    """price > ma_20, abs(ma_20 - ma_50) / ma_50 < 2% → sideways."""
    data = _entry_data(price=52_000.0, rsi=30, at_lower=True,
                       ma20=51_000.0, ma50=51_100.0)  # spread < 2%
    result = await dca.analyze(data)
    # sideways + oversold RSI + at_lower_bb + volume ok → ENTRY
    assert result["action"] == "DCA_ENTRY"


@pytest.mark.asyncio
async def test_dca_uptrend_returns_wait(dca):
    """price > ma_20 and ma_20 >> ma_50 (big spread) → uptrend → WAIT."""
    data = _entry_data(price=60_000.0, rsi=30, at_lower=True,
                       ma20=59_000.0, ma50=50_000.0)  # spread ~18%
    result = await dca.analyze(data)
    # trend_ok=False → WAIT
    assert result["action"] == "WAIT"


def test_dca_analyze_trend_downtrend():
    dca = DCAOptimizedStrategy()
    trend = dca._analyze_trend({"current_price": 45_000, "ma_20": 48_000, "ma_50": 50_000})
    assert trend == "downtrend"


def test_dca_check_volume_zero_avg_returns_false():
    dca = DCAOptimizedStrategy()
    assert dca._check_volume({"volume_24h": 1000, "avg_volume": 0}) is False


def test_dca_confidence_downtrend_higher_than_sideways():
    dca = DCAOptimizedStrategy()
    ind = {"rsi_oversold": True, "macd_positive_divergence": True, "bollinger_lower": True}
    c_down = dca._calculate_confidence("downtrend", ind, True)
    c_side = dca._calculate_confidence("sideways", ind, True)
    assert c_down > c_side


def test_dca_confidence_no_volume_lower():
    dca = DCAOptimizedStrategy()
    ind = {"rsi_oversold": True, "macd_positive_divergence": False, "bollinger_lower": False}
    c_vol = dca._calculate_confidence("downtrend", ind, True)
    c_no = dca._calculate_confidence("downtrend", ind, False)
    assert c_vol > c_no


def test_dca_explain_reasoning_includes_trend():
    dca = DCAOptimizedStrategy()
    ind = {"rsi_oversold": True, "macd_positive_divergence": False, "bollinger_lower": False}
    reason = dca._explain_reasoning("sideways", ind, True)
    assert "sideways" in reason
    assert "rsi_oversold" in reason


def test_dca_get_parameters_keys(dca):
    params = dca.get_parameters()
    for key in ("name", "risk_profile", "position_size_pct", "num_entries"):
        assert key in params


def test_dca_custom_config_respected(dca_custom):
    assert dca_custom.position_size_pct == pytest.approx(3.0)
    assert dca_custom.num_entries == 2
    assert dca_custom.rsi_oversold == 40


# ─────────────────────────────────────────────────────────────────────────────
# MeanReversionStrategy
# ─────────────────────────────────────────────────────────────────────────────

class _MockIndicators:
    def __init__(self, *, rsi=None, bb_lower=None, bb_upper=None,
                 bb_middle=None, atr=None, volume_ratio=None, stochastic_k=None):
        self.rsi = rsi
        self.bb_lower = bb_lower
        self.bb_upper = bb_upper
        self.bb_middle = bb_middle
        self.atr = atr
        self.volume_ratio = volume_ratio
        self.stochastic_k = stochastic_k


@pytest.mark.asyncio
async def test_mr_hold_when_no_indicators():
    strat = MeanReversionStrategy()
    result = await strat.analyze({"current_price": 50_000.0})
    assert result["action"] == "hold"


@pytest.mark.asyncio
async def test_mr_hold_when_price_zero():
    strat = MeanReversionStrategy()
    ind = _MockIndicators(rsi=20.0, bb_lower=49_000.0)
    result = await strat.analyze({"indicators": ind, "current_price": 0.0})
    assert result["action"] == "hold"


@pytest.mark.asyncio
async def test_mr_hold_in_strong_uptrend():
    strat = MeanReversionStrategy()
    ind = _MockIndicators(rsi=20.0, bb_lower=49_500.0)
    result = await strat.analyze({
        "indicators": ind,
        "current_price": 49_000.0,
        "regime": "strong_uptrend",
    })
    assert result["action"] == "hold"


@pytest.mark.asyncio
async def test_mr_hold_in_strong_downtrend():
    strat = MeanReversionStrategy()
    ind = _MockIndicators(rsi=80.0, bb_upper=50_200.0)
    result = await strat.analyze({
        "indicators": ind,
        "current_price": 50_500.0,
        "regime": "strong_downtrend",
    })
    assert result["action"] == "hold"


@pytest.mark.asyncio
async def test_mr_long_entry_oversold():
    strat = MeanReversionStrategy()
    ind = _MockIndicators(rsi=20.0, bb_lower=50_200.0, bb_middle=51_000.0, atr=300.0)
    result = await strat.analyze({
        "indicators": ind,
        "current_price": 50_000.0,
        "regime": "sideways",
    })
    assert result["action"] == "buy"
    assert result["direction"] == "long"
    assert result["stop_loss"] < result["entry"]
    assert result["take_profit"] == pytest.approx(51_000.0)
    assert result["confidence"] >= 0.60


@pytest.mark.asyncio
async def test_mr_long_no_bb_middle_uses_rr_fallback():
    strat = MeanReversionStrategy()
    ind = _MockIndicators(rsi=25.0, bb_lower=50_500.0, bb_middle=None, atr=200.0)
    result = await strat.analyze({
        "indicators": ind,
        "current_price": 50_000.0,
    })
    assert result["action"] == "buy"
    assert result["take_profit"] > result["entry"]


@pytest.mark.asyncio
async def test_mr_short_entry_overbought():
    strat = MeanReversionStrategy()
    ind = _MockIndicators(rsi=80.0, bb_upper=49_500.0, bb_middle=49_000.0, atr=300.0)
    result = await strat.analyze({
        "indicators": ind,
        "current_price": 50_000.0,
    })
    assert result["action"] == "sell"
    assert result["direction"] == "short"
    assert result["stop_loss"] > result["entry"]
    assert result["take_profit"] == pytest.approx(49_000.0)


@pytest.mark.asyncio
async def test_mr_short_no_bb_middle_uses_rr_fallback():
    strat = MeanReversionStrategy()
    ind = _MockIndicators(rsi=75.0, bb_upper=49_500.0, bb_middle=None, atr=200.0)
    result = await strat.analyze({
        "indicators": ind,
        "current_price": 50_000.0,
    })
    assert result["action"] == "sell"
    assert result["take_profit"] < result["entry"]


@pytest.mark.asyncio
async def test_mr_hold_rsi_in_normal_range():
    strat = MeanReversionStrategy()
    ind = _MockIndicators(rsi=50.0, bb_lower=49_000.0, bb_upper=51_000.0)
    result = await strat.analyze({
        "indicators": ind,
        "current_price": 50_000.0,
    })
    assert result["action"] == "hold"


@pytest.mark.asyncio
async def test_mr_atr_fallback_when_none():
    """ATR=None → falls back to price * 0.005."""
    strat = MeanReversionStrategy()
    ind = _MockIndicators(rsi=20.0, bb_lower=50_200.0, bb_middle=51_000.0, atr=None)
    result = await strat.analyze({
        "indicators": ind,
        "current_price": 50_000.0,
    })
    assert result["action"] == "buy"
    # stop = 50000 - 2 * (50000 * 0.005) = 50000 - 500 = 49500
    assert result["stop_loss"] == pytest.approx(49_500.0)


def test_mr_confidence_long_deep_oversold():
    strat = MeanReversionStrategy()
    ind = _MockIndicators(volume_ratio=2.0, stochastic_k=15.0)
    conf = strat._confidence(5.0, "long", ind)
    assert conf >= 0.80   # base 0.6 + oversold bonus + volume + stoch


def test_mr_confidence_short_deep_overbought():
    strat = MeanReversionStrategy()
    ind = _MockIndicators(volume_ratio=2.0, stochastic_k=85.0)
    conf = strat._confidence(95.0, "short", ind)
    assert conf >= 0.80


def test_mr_confidence_short_stoch_below_80_no_bonus():
    strat = MeanReversionStrategy()
    ind = _MockIndicators(stochastic_k=75.0)  # < 80 → no bonus
    conf_low_k = strat._confidence(75.0, "short", ind)
    ind2 = _MockIndicators(stochastic_k=85.0)  # > 80 → bonus
    conf_high_k = strat._confidence(75.0, "short", ind2)
    assert conf_high_k > conf_low_k


def test_mr_confidence_rsi_none():
    strat = MeanReversionStrategy()
    conf = strat._confidence(None, "long", _MockIndicators())
    assert conf == pytest.approx(0.60)


def test_mr_get_parameters_keys():
    strat = MeanReversionStrategy()
    p = strat.get_parameters()
    for key in ("name", "risk_profile", "rsi_oversold", "rsi_overbought"):
        assert key in p


def test_mr_hold_static():
    result = MeanReversionStrategy._hold("test reason")
    assert result["action"] == "hold"
    assert result["confidence"] == pytest.approx(0.05)
    assert result["reason"] == "test reason"
