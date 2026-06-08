"""Unit tests for BehavioralGuard and PatternScanner."""
from __future__ import annotations

import math
import pytest

from src.agents.behavioral_guard import BehavioralGuard
from src.analysis.pattern_scanner import PatternScanner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_trades(pnl_sequence: list, size: float = 2.0) -> list:
    """Create a trade history list from a sequence of P&Ls (newest first)."""
    return [{"pnl": p, "position_size_pct": size} for p in pnl_sequence]


def _make_ohlcv_trend(n: int, base: float = 50000.0, slope: float = 0.001) -> list:
    """Deterministic trending OHLCV data with clear pivot points."""
    candles = []
    for i in range(n):
        close = base * (1 + slope * i) * (1 + 0.01 * math.sin(2 * math.pi * i / 8))
        open_ = base * (1 + slope * (i - 1)) * (1 + 0.01 * math.sin(2 * math.pi * (i - 1) / 8))
        high = max(open_, close) * 1.005
        low = min(open_, close) * 0.995
        candles.append([i * 3600000, open_, high, low, close, 1000.0])
    return candles


def _make_ohlcv_range(n: int, base: float = 50000.0, amplitude: float = 0.02) -> list:
    """Oscillating OHLCV with clear support and resistance."""
    candles = []
    for i in range(n):
        close = base * (1 + amplitude * math.sin(2 * math.pi * i / 10))
        open_ = base * (1 + amplitude * math.sin(2 * math.pi * (i - 1) / 10))
        high = max(open_, close) * 1.003
        low = min(open_, close) * 0.997
        candles.append([i * 3600000, open_, high, low, close, 1000.0])
    return candles


# ---------------------------------------------------------------------------
# BehavioralGuard
# ---------------------------------------------------------------------------

class TestBehavioralGuard:
    def test_no_trades_no_alert(self):
        guard = BehavioralGuard()
        result = guard.check({"position_size_pct": 3.0}, [])
        assert result.detected is False

    def test_revenge_trading_detected(self):
        # 2 consecutive losses, then proposed trade at 2× average
        history = _make_trades([-1.0, -1.0, 1.0, 1.0], size=2.0)
        guard = BehavioralGuard()
        new_trade = {"position_size_pct": 4.0}   # 2× avg = revenge sizing
        result = guard.check(new_trade, history)
        assert result.detected is True
        assert result.kind == "revenge_trading"
        assert result.recommended_size_multiplier == 0.5
        assert result.action == "reduce_size"

    def test_no_revenge_after_single_loss(self):
        # Only 1 loss — below the 2-loss threshold
        history = _make_trades([-1.0, 1.0, 1.0], size=2.0)
        guard = BehavioralGuard()
        result = guard.check({"position_size_pct": 4.0}, history)
        assert result.detected is False

    def test_no_revenge_when_size_normal(self):
        # 2 losses but proposed size is within normal range
        history = _make_trades([-1.0, -1.0, 1.0], size=2.0)
        guard = BehavioralGuard()
        result = guard.check({"position_size_pct": 2.5}, history)
        assert result.detected is False

    def test_euphoria_detected(self):
        # 3 consecutive wins, then proposed trade 25% bigger
        history = _make_trades([1.0, 1.0, 1.0, -0.5], size=2.0)
        guard = BehavioralGuard()
        new_trade = {"position_size_pct": 2.6}  # 1.3× average → above 1.2× threshold
        result = guard.check(new_trade, history)
        assert result.detected is True
        assert result.kind == "euphoria"
        assert result.action == "force_kelly_half"

    def test_no_euphoria_when_size_normal(self):
        history = _make_trades([1.0, 1.0, 1.0], size=2.0)
        guard = BehavioralGuard()
        result = guard.check({"position_size_pct": 2.1}, history)
        assert result.detected is False

    def test_overconfidence_detected(self):
        # win_rate = 0.4, signal confidence = 0.7 → 0.30 gap > 0.15 threshold
        history = _make_trades([1.0, -1.0, -1.0], size=2.0)
        guard = BehavioralGuard()
        result = guard.check(
            {"position_size_pct": 2.0, "confidence": 0.70},
            history,
            win_rate=0.4,
        )
        assert result.detected is True
        assert result.kind == "overconfidence"
        assert result.action == "cap_confidence"
        assert result.recommended_confidence_cap == 0.4

    def test_no_overconfidence_when_aligned(self):
        guard = BehavioralGuard()
        result = guard.check(
            {"position_size_pct": 2.0, "confidence": 0.55},
            _make_trades([1.0, 1.0, -1.0]),
            win_rate=0.6,
        )
        assert result.detected is False

    def test_revenge_takes_priority_over_overconfidence(self):
        # Both revenge AND overconfidence conditions met — revenge fires first
        history = _make_trades([-1.0, -1.0, -1.0], size=2.0)
        guard = BehavioralGuard()
        result = guard.check(
            {"position_size_pct": 4.0, "confidence": 0.9},
            history,
            win_rate=0.3,
        )
        assert result.kind == "revenge_trading"


# ---------------------------------------------------------------------------
# PatternScanner
# ---------------------------------------------------------------------------

class TestPatternScanner:
    def test_returns_empty_for_too_few_candles(self):
        scanner = PatternScanner()
        assert scanner.scan([]) == []
        assert scanner.scan(_make_ohlcv_range(10)) == []

    def test_scan_returns_list(self):
        ohlcv = _make_ohlcv_range(100)
        scanner = PatternScanner()
        results = scanner.scan(ohlcv)
        assert isinstance(results, list)

    def test_results_sorted_by_confidence(self):
        ohlcv = _make_ohlcv_trend(100, slope=0.002)
        scanner = PatternScanner()
        results = scanner.scan(ohlcv)
        if len(results) >= 2:
            for i in range(len(results) - 1):
                assert results[i].confidence >= results[i + 1].confidence

    def test_pattern_result_structure(self):
        ohlcv = _make_ohlcv_range(80)
        scanner = PatternScanner()
        results = scanner.scan(ohlcv)
        for r in results:
            assert hasattr(r, "pattern")
            assert hasattr(r, "confidence")
            assert hasattr(r, "direction")
            assert hasattr(r, "target_price")
            assert 0.0 <= r.confidence <= 1.0
            assert r.direction in ("bullish", "bearish", "neutral")

    def test_double_bottom_on_v_shape(self):
        """Manually crafted V-shaped double bottom."""
        # Build: down to 45000, recover, down to 45000 again, recover
        candles = []
        prices = (
            [50000] * 5
            + [49000, 48000, 47000, 46000, 45000]  # first leg down
            + [46000, 47000, 48000, 49000, 50000]  # first recover
            + [49000, 48000, 47000, 46000, 45100]  # second leg down (near same)
            + [46000, 47000, 48000, 49000, 50000]  # second recover
            + [50000] * 5
        )
        for i, p in enumerate(prices):
            candles.append([i * 3600000, p, p * 1.003, p * 0.997, p, 1000.0])

        scanner = PatternScanner(pivot_lookback=3)
        results = scanner.scan(candles)
        bottoms = [r for r in results if r.pattern == "double_bottom"]
        assert len(bottoms) > 0
        assert bottoms[0].direction == "bullish"

    def test_double_top_on_inverted_v(self):
        """Manually crafted inverted V double top."""
        prices = (
            [50000] * 5
            + [51000, 52000, 53000, 54000, 55000]  # first leg up
            + [54000, 53000, 52000, 51000, 50000]  # first pullback
            + [51000, 52000, 53000, 54000, 54900]  # second leg up (near same)
            + [54000, 53000, 52000, 51000, 50000]  # second decline
            + [50000] * 5
        )
        candles = [[i * 3600000, p, p * 1.003, p * 0.997, p, 1000.0] for i, p in enumerate(prices)]
        scanner = PatternScanner(pivot_lookback=3)
        results = scanner.scan(candles)
        tops = [r for r in results if r.pattern == "double_top"]
        assert len(tops) > 0
        assert tops[0].direction == "bearish"
