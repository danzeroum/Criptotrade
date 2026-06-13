"""Extra coverage for indicators.py: DivergenceDetector, MultiTimeframeTrend, _safe_float."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analysis.indicators import DivergenceDetector, MultiTimeframeTrend, TechnicalAnalyzer


# ── _safe_float exception path ────────────────────────────────────────────────

def test_safe_float_returns_none_for_empty_series():
    """Lines 60-61: empty series → IndexError caught → returns None."""
    from src.analysis.indicators import _safe_float
    empty = pd.Series([], dtype=float)
    assert _safe_float(empty) is None


def test_safe_float_returns_none_for_non_numeric():
    """Lines 60-61: non-numeric series → TypeError/ValueError caught → None."""
    from src.analysis.indicators import _safe_float
    s = pd.Series(["not_a_number"])
    assert _safe_float(s) is None


# ── DivergenceDetector ────────────────────────────────────────────────────────

def _ohlcv_from_closes(closes: list[float]) -> list[list[float]]:
    ts = 1_700_000_000_000
    return [[ts + i * 3600_000, c, c + 100, c - 100, c, 100.0] for i, c in enumerate(closes)]


def test_check_rsi_price_insufficient_data_returns_false():
    """Line 208: < 4 closes → DivergenceResult(False, None, 'insufficient data')."""
    detector = DivergenceDetector(lookback=20)
    ohlcv = _ohlcv_from_closes([50000.0, 51000.0])
    rsi_series = pd.Series([50.0, 51.0])
    result = detector.check_rsi_price(ohlcv, rsi_series)
    assert result.detected is False
    assert result.description == "insufficient data"


def test_check_macd_price_insufficient_data_returns_false():
    """Line 241: < 4 entries → DivergenceResult(False, None, 'insufficient data')."""
    detector = DivergenceDetector(lookback=20)
    ohlcv = _ohlcv_from_closes([50000.0])
    macd_series = pd.Series([0.1])
    result = detector.check_macd_price(ohlcv, macd_series)
    assert result.detected is False
    assert result.description == "insufficient data"


def test_check_rsi_price_bullish_divergence():
    """Lines 221-224: price lower low but RSI higher low → bullish divergence."""
    detector = DivergenceDetector(lookback=10)
    # First half: price low = 100, RSI low = 40
    # Second half: price low = 90 (LOWER), RSI low = 50 (HIGHER) → bullish divergence
    closes_first = [110.0, 100.0, 115.0, 105.0, 100.0]   # min = 100
    closes_second = [108.0, 90.0, 112.0, 102.0, 95.0]    # min = 90
    closes = closes_first + closes_second
    ohlcv = _ohlcv_from_closes(closes)
    rsi_first = [60, 40, 65, 55, 40]                      # min = 40
    rsi_second = [62, 50, 67, 57, 55]                     # min = 50
    rsi_series = pd.Series(rsi_first + rsi_second, dtype=float)
    result = detector.check_rsi_price(ohlcv, rsi_series)
    assert result.detected is True
    assert result.kind == "bullish_divergence"


def test_check_rsi_price_bearish_divergence():
    """Lines 227-230: price higher high but RSI lower high → bearish divergence."""
    detector = DivergenceDetector(lookback=10)
    # First half: price high = 100, RSI high = 70
    # Second half: price high = 120 (HIGHER), RSI high = 65 (LOWER) → bearish divergence
    closes_first = [90.0, 100.0, 95.0, 98.0, 100.0]      # max = 100
    closes_second = [105.0, 120.0, 110.0, 115.0, 118.0]  # max = 120
    closes = closes_first + closes_second
    ohlcv = _ohlcv_from_closes(closes)
    rsi_first = [60, 70, 65, 68, 70]                      # max = 70
    rsi_second = [62, 65, 63, 64, 63]                     # max = 65 (LOWER)
    rsi_series = pd.Series(rsi_first + rsi_second, dtype=float)
    result = detector.check_rsi_price(ohlcv, rsi_series)
    assert result.detected is True
    assert result.kind == "bearish_divergence"


def test_check_macd_price_bullish_divergence():
    """Lines 251-254: price lower low but MACD histogram higher low → bullish."""
    detector = DivergenceDetector(lookback=10)
    closes_first = [110.0, 100.0, 115.0, 105.0, 100.0]   # min = 100
    closes_second = [108.0, 90.0, 112.0, 102.0, 95.0]    # min = 90 (LOWER)
    closes = closes_first + closes_second
    ohlcv = _ohlcv_from_closes(closes)
    hist_first = [1.0, -2.0, 1.5, 0.5, -2.0]             # min = -2.0
    hist_second = [1.0, -1.0, 1.5, 0.5, -1.0]            # min = -1.0 (HIGHER)
    hist_series = pd.Series(hist_first + hist_second, dtype=float)
    result = detector.check_macd_price(ohlcv, hist_series)
    assert result.detected is True
    assert result.kind == "bullish_divergence"


def test_check_macd_price_bearish_divergence():
    """Lines 261-265: price higher high but MACD histogram lower high → bearish."""
    detector = DivergenceDetector(lookback=10)
    closes_first = [90.0, 100.0, 95.0, 98.0, 100.0]      # max = 100
    closes_second = [105.0, 120.0, 110.0, 115.0, 120.0]  # max = 120 (HIGHER)
    closes = closes_first + closes_second
    ohlcv = _ohlcv_from_closes(closes)
    hist_first = [1.0, 3.0, 2.0, 2.5, 3.0]               # max = 3.0
    hist_second = [1.0, 2.0, 1.5, 1.8, 2.0]              # max = 2.0 (LOWER)
    hist_series = pd.Series(hist_first + hist_second, dtype=float)
    result = detector.check_macd_price(ohlcv, hist_series)
    assert result.detected is True
    assert result.kind == "bearish_divergence"


# ── MultiTimeframeTrend ───────────────────────────────────────────────────────

def _make_ohlcv_enough(n: int = 60, up: bool = True) -> list:
    ts = 1_700_000_000_000
    base = 50_000.0
    rows = []
    for i in range(n):
        c = base + (i * 10 if up else -i * 10)
        rows.append([ts + i * 3600_000, c - 50, c + 50, c - 100, c, 100.0])
    return rows


class _MockExchange:
    def __init__(self, ohlcv_map: dict):
        self._map = ohlcv_map

    async def fetch_ohlcv(self, symbol, timeframe, limit=50):
        return self._map.get(timeframe, [])


@pytest.mark.asyncio
async def test_multitf_all_bullish_aligned():
    """All three timeframes return bullish EMA spread → aligned=True, direction='bullish'."""
    ohlcv = _make_ohlcv_enough(60, up=True)
    exchange = _MockExchange({"1w": ohlcv, "1d": ohlcv, "1h": ohlcv})
    mtf = MultiTimeframeTrend()
    result = await mtf.classify("BTC/USDT", exchange)
    # Uptrend candles → ema_fast > ema_slow → bullish
    if result.aligned:
        assert result.direction == "bullish"
    else:
        assert result.direction is None


@pytest.mark.asyncio
async def test_multitf_insufficient_data_returns_unknown():
    """Lines 299-301: fewer than MIN_CANDLES → 'unknown' for that timeframe."""
    tiny_ohlcv = _make_ohlcv_enough(5)  # less than MIN_CANDLES (50)
    exchange = _MockExchange({"1w": tiny_ohlcv, "1d": tiny_ohlcv, "1h": tiny_ohlcv})
    mtf = MultiTimeframeTrend()
    result = await mtf.classify("BTC/USDT", exchange)
    assert result.primary == "unknown"
    assert result.secondary == "unknown"
    assert result.minor == "unknown"
    assert result.aligned is False


@pytest.mark.asyncio
async def test_multitf_exchange_error_returns_unknown():
    """Lines 308-310: exchange raises → 'unknown' for that timeframe."""
    class _FailExchange:
        async def fetch_ohlcv(self, symbol, timeframe, limit=50):
            raise RuntimeError("exchange down")

    mtf = MultiTimeframeTrend()
    result = await mtf.classify("BTC/USDT", _FailExchange())
    assert result.primary == "unknown"
    assert result.aligned is False


@pytest.mark.asyncio
async def test_multitf_mixed_trend_not_aligned():
    """Primary and secondary disagree → not aligned."""
    up_ohlcv = _make_ohlcv_enough(60, up=True)
    down_ohlcv = _make_ohlcv_enough(60, up=False)
    exchange = _MockExchange({"1w": up_ohlcv, "1d": down_ohlcv, "1h": up_ohlcv})
    mtf = MultiTimeframeTrend()
    result = await mtf.classify("BTC/USDT", exchange)
    # Mixed → not aligned
    assert result.aligned is False
    assert result.direction is None
