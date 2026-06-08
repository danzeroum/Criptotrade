"""Unit tests for technical analysis modules."""
from __future__ import annotations

import math

import pytest

from src.analysis.indicators import DivergenceDetector, TechnicalAnalyzer, TechnicalIndicators
from src.analysis.regime_detector import detect_market_extreme, detect_regime, strategies_for_regime
from src.analysis.support_resistance import SupportResistanceDetector
from src.analysis.volume_profile import VolumeProfile

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int = 100, base: float = 50000.0, amplitude: float = 0.02) -> list:
    """Generate deterministic sinusoidal OHLCV data."""
    candles = []
    for i in range(n):
        ts = i * 3600 * 1000  # 1h candles
        close = base * (1 + amplitude * math.sin(2 * math.pi * i / 20))
        open_ = base * (1 + amplitude * math.sin(2 * math.pi * (i - 1) / 20))
        high = max(open_, close) * 1.002
        low = min(open_, close) * 0.998
        volume = 1000.0 + 100.0 * math.sin(2 * math.pi * i / 10)
        candles.append([ts, open_, high, low, close, volume])
    return candles


# ---------------------------------------------------------------------------
# TechnicalAnalyzer
# ---------------------------------------------------------------------------

class TestTechnicalAnalyzer:
    def test_get_latest_returns_indicators(self):
        ohlcv = _make_ohlcv(100)
        analyzer = TechnicalAnalyzer(ohlcv)
        ind = analyzer.get_latest()

        assert isinstance(ind, TechnicalIndicators)
        assert ind.current_price is not None
        assert ind.current_price > 0

    def test_rsi_in_range(self):
        ind = TechnicalAnalyzer(_make_ohlcv(100)).get_latest()
        assert ind.rsi is not None
        assert 0 < ind.rsi < 100

    def test_bollinger_bands_ordered(self):
        ind = TechnicalAnalyzer(_make_ohlcv(100)).get_latest()
        assert ind.bb_upper is not None
        assert ind.bb_middle is not None
        assert ind.bb_lower is not None
        assert ind.bb_upper > ind.bb_middle > ind.bb_lower

    def test_macd_components_present(self):
        ind = TechnicalAnalyzer(_make_ohlcv(100)).get_latest()
        assert ind.macd_line is not None
        assert ind.macd_signal is not None
        assert ind.macd_hist is not None

    def test_atr_positive(self):
        ind = TechnicalAnalyzer(_make_ohlcv(100)).get_latest()
        assert ind.atr is not None
        assert ind.atr > 0

    def test_ema_fast_and_slow_present(self):
        ind = TechnicalAnalyzer(_make_ohlcv(100)).get_latest()
        assert ind.ema_fast is not None
        assert ind.ema_slow is not None

    def test_volume_ratio_present(self):
        ind = TechnicalAnalyzer(_make_ohlcv(100)).get_latest()
        assert ind.volume_ratio is not None
        assert ind.volume_ratio > 0

    def test_requires_minimum_candles(self):
        with pytest.raises(ValueError, match="50"):
            TechnicalAnalyzer(_make_ohlcv(10))

    def test_get_series_returns_pandas_series(self):
        import pandas as pd
        analyzer = TechnicalAnalyzer(_make_ohlcv(100))
        rsi_series = analyzer.get_series("rsi")
        assert isinstance(rsi_series, pd.Series)
        assert len(rsi_series) == 100


# ---------------------------------------------------------------------------
# DivergenceDetector
# ---------------------------------------------------------------------------

class TestDivergenceDetector:
    def test_no_divergence_on_uniform_data(self):
        ohlcv = _make_ohlcv(60)
        analyzer = TechnicalAnalyzer(ohlcv)
        rsi_series = analyzer.get_series("rsi")
        detector = DivergenceDetector(lookback=20)
        result = detector.check_rsi_price(ohlcv, rsi_series)
        # Result should be a DivergenceResult with a boolean detected
        assert hasattr(result, "detected")
        assert hasattr(result, "kind")

    def test_macd_divergence_result_structure(self):
        ohlcv = _make_ohlcv(60)
        analyzer = TechnicalAnalyzer(ohlcv)
        macd_hist = analyzer.get_series("macd_hist")
        detector = DivergenceDetector(lookback=20)
        result = detector.check_macd_price(ohlcv, macd_hist)
        assert hasattr(result, "detected")


# ---------------------------------------------------------------------------
# SupportResistanceDetector
# ---------------------------------------------------------------------------

class TestSupportResistanceDetector:
    def test_detect_returns_sr_levels(self):
        ohlcv = _make_ohlcv(100)
        detector = SupportResistanceDetector()
        result = detector.detect(ohlcv)
        assert hasattr(result, "support")
        assert hasattr(result, "resistance")
        assert hasattr(result, "zones")

    def test_insufficient_data_returns_empty(self):
        detector = SupportResistanceDetector(lookback=5)
        result = detector.detect(_make_ohlcv(5))
        assert result.support is None
        assert result.resistance is None

    def test_fibonacci_levels_structure(self):
        levels = SupportResistanceDetector.fibonacci_levels(40000, 50000)
        assert "0.0%" in levels
        assert "100.0%" in levels
        assert "61.8%" in levels
        assert levels["0.0%"] == levels["100.0%"] + (50000 - 40000)
        # 0% = swing_high (50000), 100% = swing_low (40000) in standard retracement
        assert levels["100.0%"] == 40000
        assert levels["0.0%"] == 50000

    def test_fibonacci_levels_ordered(self):
        levels = SupportResistanceDetector.fibonacci_levels(40000, 50000)
        sorted_values = sorted(levels.values())
        assert sorted_values[0] == levels["100.0%"]
        assert sorted_values[-1] == levels["0.0%"]


# ---------------------------------------------------------------------------
# VolumeProfile
# ---------------------------------------------------------------------------

class TestVolumeProfile:
    def test_analyze_returns_poc(self):
        ohlcv = _make_ohlcv(100)
        vp = VolumeProfile(ohlcv)
        result = vp.analyze()
        assert result.poc > 0
        assert result.value_area_high >= result.value_area_low

    def test_poc_within_price_range(self):
        ohlcv = _make_ohlcv(100)
        closes = [c[4] for c in ohlcv]
        vp = VolumeProfile(ohlcv)
        result = vp.analyze()
        assert min(closes) * 0.999 <= result.poc <= max(closes) * 1.001

    def test_value_area_contains_poc(self):
        vp = VolumeProfile(_make_ohlcv(100))
        r = vp.analyze()
        assert r.value_area_low <= r.poc <= r.value_area_high

    def test_handles_single_candle(self):
        ohlcv = [[0, 50000, 50500, 49500, 50000, 100]]
        vp = VolumeProfile(ohlcv)
        result = vp.analyze()
        assert result.poc > 0


# ---------------------------------------------------------------------------
# RegimeDetector
# ---------------------------------------------------------------------------

class TestRegimeDetector:
    def test_sideways_when_ema_spread_small(self):
        regime = detect_regime(
            ema_fast=50100.0, ema_slow=50000.0,
            atr=200.0, current_price=50000.0
        )
        # ema_spread = 100/50000 = 0.2% < 1% → sideways
        assert regime == "sideways"

    def test_strong_uptrend_when_ema_spread_large_bullish(self):
        regime = detect_regime(
            ema_fast=52000.0, ema_slow=50000.0,
            atr=300.0, current_price=51000.0
        )
        # ema_spread = 2000/51000 ≈ 3.9% > 2% → strong_uptrend
        assert regime == "strong_uptrend"

    def test_strong_downtrend_when_ema_spread_large_bearish(self):
        regime = detect_regime(
            ema_fast=48000.0, ema_slow=50000.0,
            atr=300.0, current_price=49000.0
        )
        assert regime == "strong_downtrend"

    def test_chaotic_when_high_volatility(self):
        regime = detect_regime(
            ema_fast=50100.0, ema_slow=50000.0,
            atr=3000.0, current_price=50000.0
        )
        # atr/price = 3000/50000 = 6% > 5% → chaotic
        assert regime == "chaotic"

    def test_unknown_when_missing_params(self):
        regime = detect_regime(None, None, None, None)
        assert regime == "unknown"

    def test_strategies_for_sideways(self):
        strategies = strategies_for_regime("sideways")
        assert "grid" in strategies
        assert "dca" in strategies

    def test_strategies_for_chaotic_empty(self):
        strategies = strategies_for_regime("chaotic")
        assert strategies == []

    def test_detect_market_extreme_euphoria(self):
        result = detect_market_extreme(rsi=80, volume_ratio=2.5)
        assert result is not None
        assert "EUFORIA" in result

    def test_detect_market_extreme_panic(self):
        result = detect_market_extreme(rsi=20, volume_ratio=2.5)
        assert result is not None
        assert "PÂNICO" in result

    def test_detect_market_extreme_none_when_neutral(self):
        result = detect_market_extreme(rsi=50, volume_ratio=1.0)
        assert result is None
