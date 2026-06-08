"""Chart pattern scanner.

Murphy (*Technical Analysis of Financial Markets*): "Chart patterns are the
language of the market. Reversal patterns warn of trend exhaustion; continuation
patterns signal trend resumption."

Patterns detected:
  Reversal   — Head & Shoulders, Double Top / Bottom
  Continuation — Ascending / Descending Triangle, Rectangle
  Note: Flag, Pennant, Wedge detection requires minimum 30+ candles and
        is left for future enhancement when data fidelity improves.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

# Minimum candles required for meaningful pattern detection
MIN_CANDLES_PATTERN = 30
# Tolerance for price level comparisons (0.5% of price)
TOLERANCE_PCT = 0.005


@dataclass
class PatternResult:
    """A detected chart pattern."""
    pattern: str         # e.g. "head_and_shoulders", "double_top"
    confidence: float    # 0.0 – 1.0
    direction: str       # "bearish" | "bullish" | "neutral"
    target_price: float | None  # measured-move target, None when unavailable
    candle_index: int    # index of the pattern's completion candle
    description: str = ""


class PatternScanner:
    """Scan OHLCV data for common chart patterns.

    Usage::

        scanner = PatternScanner()
        results = scanner.scan(ohlcv)
        for r in results:
            if r.confidence > 0.7:
                print(r.pattern, r.direction, r.target_price)
    """

    def __init__(self, pivot_lookback: int = 5) -> None:
        self.pivot_lookback = pivot_lookback

    def scan(self, ohlcv: list) -> list[PatternResult]:
        """Scan all candles and return detected patterns (newest first).

        Only patterns with confidence > 0 are returned. Results are sorted
        by confidence descending.
        """
        if len(ohlcv) < MIN_CANDLES_PATTERN:
            return []

        closes = np.array([c[4] for c in ohlcv], dtype=float)
        highs = np.array([c[2] for c in ohlcv], dtype=float)
        lows = np.array([c[3] for c in ohlcv], dtype=float)

        pivot_highs = self._find_pivot_highs(highs)
        pivot_lows = self._find_pivot_lows(lows)

        results: list[PatternResult] = []
        results.extend(self._check_double_top(highs, closes, pivot_highs))
        results.extend(self._check_double_bottom(lows, closes, pivot_lows))
        results.extend(self._check_head_and_shoulders(highs, lows, closes, pivot_highs))
        results.extend(self._check_ascending_triangle(highs, lows, pivot_highs, pivot_lows))
        results.extend(self._check_descending_triangle(highs, lows, pivot_highs, pivot_lows))
        results.extend(self._check_rectangle(highs, lows, closes, pivot_highs, pivot_lows))

        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    # ---------------------------------------------------------------- patterns

    def _check_double_top(
        self, highs: np.ndarray, closes: np.ndarray, pivot_highs: list[int]
    ) -> list[PatternResult]:
        """Two consecutive highs at approximately the same price level."""
        results = []
        for i in range(1, len(pivot_highs)):
            a, b = pivot_highs[i - 1], pivot_highs[i]
            if highs[b] < closes[-1]:
                continue  # pattern must be in recent history
            if abs(highs[a] - highs[b]) / highs[a] < TOLERANCE_PCT:
                # Two similar highs with a trough between them
                trough_low = closes[a:b].min() if b > a else closes[a]
                neckline = float(trough_low)
                target = highs[b] - (highs[b] - neckline)
                confidence = self._similarity_confidence(highs[a], highs[b])
                results.append(PatternResult(
                    pattern="double_top",
                    confidence=confidence,
                    direction="bearish",
                    target_price=round(target, 2),
                    candle_index=b,
                    description=f"Double top at ~{highs[b]:.0f}, neckline {neckline:.0f}",
                ))
        return results

    def _check_double_bottom(
        self, lows: np.ndarray, closes: np.ndarray, pivot_lows: list[int]
    ) -> list[PatternResult]:
        """Two consecutive lows at approximately the same price level."""
        results = []
        for i in range(1, len(pivot_lows)):
            a, b = pivot_lows[i - 1], pivot_lows[i]
            if abs(lows[a] - lows[b]) / lows[a] < TOLERANCE_PCT:
                peak_high = closes[a:b].max() if b > a else closes[a]
                neckline = float(peak_high)
                target = lows[b] + (neckline - lows[b])
                confidence = self._similarity_confidence(lows[a], lows[b])
                results.append(PatternResult(
                    pattern="double_bottom",
                    confidence=confidence,
                    direction="bullish",
                    target_price=round(target, 2),
                    candle_index=b,
                    description=f"Double bottom at ~{lows[b]:.0f}, neckline {neckline:.0f}",
                ))
        return results

    def _check_head_and_shoulders(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        pivot_highs: list[int],
    ) -> list[PatternResult]:
        """Head (middle) is higher than left and right shoulders."""
        results = []
        if len(pivot_highs) < 3:
            return results
        for i in range(len(pivot_highs) - 2):
            ls, h, rs = pivot_highs[i], pivot_highs[i + 1], pivot_highs[i + 2]
            head_h = highs[h]
            ls_h = highs[ls]
            rs_h = highs[rs]
            # Head must be higher than both shoulders
            if not (head_h > ls_h and head_h > rs_h):
                continue
            # Shoulders should be roughly equal
            if abs(ls_h - rs_h) / ls_h > 0.03:
                continue
            # Neckline from troughs between shoulders and head
            neckline_left = float(lows[ls:h].min()) if h > ls else float(lows[ls])
            neckline_right = float(lows[h:rs].min()) if rs > h else float(lows[h])
            neckline = (neckline_left + neckline_right) / 2.0
            target = neckline - (head_h - neckline)
            confidence = 0.55 + 0.15 * (1.0 - abs(ls_h - rs_h) / ls_h / 0.03)
            confidence = min(confidence, 0.85)
            results.append(PatternResult(
                pattern="head_and_shoulders",
                confidence=round(confidence, 3),
                direction="bearish",
                target_price=round(target, 2),
                candle_index=rs,
                description=f"H&S: shoulders {ls_h:.0f}/{rs_h:.0f}, head {head_h:.0f}",
            ))
        return results

    def _check_ascending_triangle(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        pivot_highs: list[int],
        pivot_lows: list[int],
    ) -> list[PatternResult]:
        """Flat resistance top, rising support lows."""
        if len(pivot_highs) < 2 or len(pivot_lows) < 2:
            return []
        top_a, top_b = highs[pivot_highs[-2]], highs[pivot_highs[-1]]
        bot_a, bot_b = lows[pivot_lows[-2]], lows[pivot_lows[-1]]
        # Resistance is flat (within 1%)
        if abs(top_a - top_b) / top_a > 0.01:
            return []
        # Support is rising
        if bot_b <= bot_a:
            return []
        resistance = (top_a + top_b) / 2.0
        height = resistance - bot_a
        target = resistance + height
        confidence = 0.55 + 0.10 * min((bot_b - bot_a) / bot_a / 0.02, 1.0)
        return [PatternResult(
            pattern="ascending_triangle",
            confidence=round(confidence, 3),
            direction="bullish",
            target_price=round(target, 2),
            candle_index=pivot_lows[-1],
            description=f"Ascending triangle, resistance ~{resistance:.0f}",
        )]

    def _check_descending_triangle(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        pivot_highs: list[int],
        pivot_lows: list[int],
    ) -> list[PatternResult]:
        """Flat support bottom, descending resistance highs."""
        if len(pivot_highs) < 2 or len(pivot_lows) < 2:
            return []
        top_a, top_b = highs[pivot_highs[-2]], highs[pivot_highs[-1]]
        bot_a, bot_b = lows[pivot_lows[-2]], lows[pivot_lows[-1]]
        # Support is flat (within 1%)
        if abs(bot_a - bot_b) / bot_a > 0.01:
            return []
        # Resistance is declining
        if top_b >= top_a:
            return []
        support = (bot_a + bot_b) / 2.0
        height = top_a - support
        target = support - height
        confidence = 0.55 + 0.10 * min((top_a - top_b) / top_a / 0.02, 1.0)
        return [PatternResult(
            pattern="descending_triangle",
            confidence=round(confidence, 3),
            direction="bearish",
            target_price=round(target, 2),
            candle_index=pivot_highs[-1],
            description=f"Descending triangle, support ~{support:.0f}",
        )]

    def _check_rectangle(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        pivot_highs: list[int],
        pivot_lows: list[int],
    ) -> list[PatternResult]:
        """Price bouncing between two roughly parallel horizontal levels."""
        if len(pivot_highs) < 2 or len(pivot_lows) < 2:
            return []
        top_a, top_b = highs[pivot_highs[-2]], highs[pivot_highs[-1]]
        bot_a, bot_b = lows[pivot_lows[-2]], lows[pivot_lows[-1]]
        # Both resistance and support are roughly flat (within 1.5% each)
        if abs(top_a - top_b) / top_a > 0.015:
            return []
        if abs(bot_a - bot_b) / bot_a > 0.015:
            return []
        resistance = (top_a + top_b) / 2.0
        support = (bot_a + bot_b) / 2.0
        height = resistance - support
        current = float(closes[-1])
        # Breakout direction hint
        if current > resistance * (1 - TOLERANCE_PCT):
            direction = "bullish"
            target = resistance + height
        elif current < support * (1 + TOLERANCE_PCT):
            direction = "bearish"
            target = support - height
        else:
            direction = "neutral"
            target = None
        confidence = 0.50 + 0.10 * min(
            1.0 - abs(top_a - top_b) / top_a / 0.015, 1.0
        )
        return [PatternResult(
            pattern="rectangle",
            confidence=round(confidence, 3),
            direction=direction,
            target_price=round(target, 2) if target else None,
            candle_index=len(closes) - 1,
            description=f"Rectangle {support:.0f}-{resistance:.0f}",
        )]

    # ----------------------------------------------------------------- helpers

    def _find_pivot_highs(self, highs: np.ndarray) -> list[int]:
        lb = self.pivot_lookback
        n = len(highs)
        return [
            i for i in range(lb, n - lb)
            if highs[i] == highs[i - lb: i + lb + 1].max()
            and np.sum(highs[i - lb: i + lb + 1] == highs[i]) == 1
        ]

    def _find_pivot_lows(self, lows: np.ndarray) -> list[int]:
        lb = self.pivot_lookback
        n = len(lows)
        return [
            i for i in range(lb, n - lb)
            if lows[i] == lows[i - lb: i + lb + 1].min()
            and np.sum(lows[i - lb: i + lb + 1] == lows[i]) == 1
        ]

    @staticmethod
    def _similarity_confidence(price_a: float, price_b: float) -> float:
        """Confidence based on how similar two price levels are."""
        if price_a <= 0:
            return 0.5
        diff_pct = abs(price_a - price_b) / price_a
        # Within TOLERANCE_PCT → 0.85 confidence; at 2% apart → 0.5
        score = 0.85 - (diff_pct / TOLERANCE_PCT) * 0.35
        return round(max(0.5, min(0.85, score)), 3)
