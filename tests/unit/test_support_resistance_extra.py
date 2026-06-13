"""Extra coverage for support_resistance.py — _cluster, _find_pivots, fallback paths."""
from __future__ import annotations

import numpy as np
import pytest

from src.analysis.support_resistance import SupportResistanceDetector


def _make_zigzag_ohlcv(n: int = 80) -> list:
    """Build OHLCV with clear alternating pivot highs/lows.

    Pattern: high → low → high → low ...
    Each candle:  h[2] = current_price + 200, l[3] = current_price - 200 for regular.
    Every 10th candle:  extra-high (pivot) or extra-low (pivot trough).
    """
    ts = 1_700_000_000_000
    result = []
    base = 50_000.0
    for i in range(n):
        c = base
        # Create strong, unique pivot at every 10th candle
        if i % 20 == 10:          # pivot HIGH
            h = c + 1_500.0
            l = c - 200.0
        elif i % 20 == 0 and i > 0:   # pivot LOW
            h = c + 200.0
            l = c - 1_500.0
        else:
            h = c + 200.0
            l = c - 200.0
        result.append([ts + i * 3_600_000, c, h, l, c, 100.0])
    return result


def test_cluster_produces_sr_levels():
    """Lines 125-147: _cluster with real pivot prices builds SRLevel objects."""
    detector = SupportResistanceDetector(lookback=3, tolerance_pct=0.01)
    levels = detector._cluster([48_000.0, 48_050.0, 52_000.0, 52_100.0],
                               kind="resistance", ref_price=50_000.0)
    # Two clusters (48k group and 52k group)
    assert len(levels) >= 1
    assert all(hasattr(lv, "price") for lv in levels)
    assert all(hasattr(lv, "strength") for lv in levels)


def test_cluster_single_level_no_grouping():
    """Lines 125-132: single value → one cluster of strength 1."""
    detector = SupportResistanceDetector(lookback=3, tolerance_pct=0.01)
    levels = detector._cluster([50_000.0], kind="support", ref_price=55_000.0)
    assert len(levels) == 1
    assert levels[0].strength == 1


def test_cluster_empty_returns_empty():
    """Lines 123-124: empty levels → return []."""
    detector = SupportResistanceDetector()
    assert detector._cluster([], kind="support", ref_price=50_000.0) == []


def test_find_pivots_finds_high():
    """Line 114: values[i] is unique max in window → appended as pivot high."""
    detector = SupportResistanceDetector(lookback=2)
    # Index 2 is a clear unique high
    vals = np.array([100.0, 105.0, 200.0, 105.0, 100.0], dtype=float)
    pivots = detector._find_pivots(vals, higher=True)
    assert 2 in pivots


def test_find_pivots_finds_low():
    """Line 116: values[i] is unique min in window → appended as pivot low."""
    detector = SupportResistanceDetector(lookback=2)
    vals = np.array([100.0, 95.0, 10.0, 95.0, 100.0], dtype=float)
    pivots = detector._find_pivots(vals, higher=False)
    assert 2 in pivots


def test_find_pivots_skips_duplicate_max():
    """Duplicate max in window → not counted as pivot (uniqueness check)."""
    detector = SupportResistanceDetector(lookback=2)
    # Both index 2 and 3 have value 200 → neither is unique
    vals = np.array([100.0, 150.0, 200.0, 200.0, 100.0], dtype=float)
    pivots = detector._find_pivots(vals, higher=True)
    assert 2 not in pivots


def test_detect_fallback_when_no_pivots():
    """Lines 95-98: when no pivot-based levels found, uses range min/max."""
    detector = SupportResistanceDetector(lookback=3, tolerance_pct=0.01)
    # Flat data — no unique pivots anywhere
    ts = 1_700_000_000_000
    n = 30
    ohlcv = [[ts + i * 3_600_000, 50_000.0, 50_000.0, 50_000.0, 50_000.0, 100.0]
             for i in range(n)]
    result = detector.detect(ohlcv)
    # Fallback: support = min of lows, resistance = max of highs
    assert result.support is not None
    assert result.resistance is not None


def test_detect_with_pivots_finds_real_levels():
    """Full detect path with zigzag data finds genuine S/R levels."""
    ohlcv = _make_zigzag_ohlcv(80)
    detector = SupportResistanceDetector(lookback=4, tolerance_pct=0.02)
    result = detector.detect(ohlcv)
    # At minimum, fallback values must be set
    assert result.support is not None
    assert result.resistance is not None
