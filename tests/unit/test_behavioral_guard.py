"""Unit tests for BehavioralGuard and PatternScanner."""
from __future__ import annotations

import math

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

    def test_head_and_shoulders(self):
        """Middle pivot clearly higher than roughly equal shoulder pivots."""
        lb = 3
        base_h = 50100.0
        base_l = 49900.0
        n = 40
        highs  = [base_h] * n
        lows   = [base_l] * n
        closes = [50000.0] * n

        # Left shoulder at 8, head at 18, right shoulder at 28
        highs[8]  = 53000.0  # shoulder 1
        highs[18] = 58000.0  # head (highest)
        highs[28] = 53300.0  # shoulder 2 (~0.6% above shoulder1 — within 3%)

        # Troughs (neckline) between pivots
        lows[13] = 49000.0
        lows[23] = 48800.0

        candles = [
            [i * 3600000, closes[i], highs[i], lows[i], closes[i], 1000.0]
            for i in range(n)
        ]
        scanner = PatternScanner(pivot_lookback=lb)
        results = scanner.scan(candles)
        hs = [r for r in results if r.pattern == "head_and_shoulders"]
        assert len(hs) > 0
        assert hs[0].direction == "bearish"
        assert hs[0].target_price is not None

    def test_ascending_triangle(self):
        """Flat resistance top, rising support lows."""
        lb = 3
        n = 40
        highs  = [50100.0] * n
        # base_l must be > 50000 so lows[30]=50000 is a genuine local minimum
        lows   = [52000.0] * n
        closes = [50000.0] * n

        # Flat resistance at 55000 / 55200 (within 1%)
        highs[10] = 55000.0
        highs[22] = 55200.0  # 0.36% apart

        # Rising support: 48000 → 50000 (both below base 52000 → genuine pivots)
        lows[16] = 48000.0
        lows[30] = 50000.0

        candles = [
            [i * 3600000, closes[i], highs[i], lows[i], closes[i], 1000.0]
            for i in range(n)
        ]
        scanner = PatternScanner(pivot_lookback=lb)
        results = scanner.scan(candles)
        at = [r for r in results if r.pattern == "ascending_triangle"]
        assert len(at) > 0
        assert at[0].direction == "bullish"

    def test_descending_triangle(self):
        """Flat support bottom, declining resistance highs."""
        lb = 3
        n = 40
        highs  = [50100.0] * n
        lows   = [49900.0] * n
        closes = [50000.0] * n

        # Declining resistance: 55000 → 52000
        highs[10] = 55000.0
        highs[22] = 52000.0

        # Flat support: 45000 / 45200 (within 1%)
        lows[16] = 45000.0
        lows[30] = 45150.0  # 0.33% apart

        candles = [
            [i * 3600000, closes[i], highs[i], lows[i], closes[i], 1000.0]
            for i in range(n)
        ]
        scanner = PatternScanner(pivot_lookback=lb)
        results = scanner.scan(candles)
        dt = [r for r in results if r.pattern == "descending_triangle"]
        assert len(dt) > 0
        assert dt[0].direction == "bearish"

    def test_rectangle_neutral(self):
        """Both highs and lows are flat → rectangle, price inside → neutral."""
        lb = 3
        n = 40
        # Close stays mid-range (50000), well inside the rectangle.
        # base_l > 45100 so both flat support pivots are genuine local minima.
        highs  = [50050.0] * n
        lows   = [46000.0] * n
        closes = [50000.0] * n

        # Flat resistance ~55000
        highs[10] = 55000.0
        highs[22] = 55200.0  # within 1.5%

        # Flat support ~45000
        lows[16] = 45000.0
        lows[30] = 45100.0  # within 1.5%

        candles = [
            [i * 3600000, closes[i], highs[i], lows[i], closes[i], 1000.0]
            for i in range(n)
        ]
        scanner = PatternScanner(pivot_lookback=lb)
        results = scanner.scan(candles)
        rects = [r for r in results if r.pattern == "rectangle"]
        assert len(rects) > 0
        assert rects[0].direction == "neutral"
        assert rects[0].target_price is None

    def test_rectangle_bullish_breakout(self):
        """Close above resistance → bullish rectangle breakout."""
        lb = 3
        n = 40
        highs  = [50050.0] * n
        lows   = [46000.0] * n  # base_l > 45100 → both support pivots genuine
        closes = [50000.0] * n
        closes[-1] = 56000.0  # breakout above ~55000

        highs[10] = 55000.0
        highs[22] = 55200.0
        lows[16]  = 45000.0
        lows[30]  = 45100.0

        candles = [
            [i * 3600000, closes[i], highs[i], lows[i], closes[i], 1000.0]
            for i in range(n)
        ]
        scanner = PatternScanner(pivot_lookback=lb)
        results = scanner.scan(candles)
        rects = [r for r in results if r.pattern == "rectangle"]
        assert len(rects) > 0
        assert rects[0].direction == "bullish"

    def test_similarity_confidence_zero_price(self):
        """_similarity_confidence with price_a=0 returns 0.5 (guard)."""
        assert PatternScanner._similarity_confidence(0.0, 100.0) == 0.5
