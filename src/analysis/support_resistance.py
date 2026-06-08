"""Support and Resistance level detection.

Uses pivot high/low detection with zone clustering.
Also computes Fibonacci retracement levels for price targets.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SRLevel:
    """A single support or resistance zone."""
    price: float
    kind: str         # "support" | "resistance"
    strength: int     # number of pivots clustered here
    last_touch: float = 0.0   # price of most recent touch


@dataclass
class SRLevels:
    """Result of support/resistance detection."""
    support: float | None
    resistance: float | None
    zones: list[SRLevel] = field(default_factory=list)


class SupportResistanceDetector:
    """Detect S/R zones using pivot high/low method.

    A pivot high is a candle whose high is greater than the N candles on each side.
    A pivot low is a candle whose low is less than the N candles on each side.
    Nearby pivots are clustered into zones (tolerance: ±0.3% of price by default).

    Murphy: "S/R zones with multiple touches are the most reliable."
    """

    def __init__(self, lookback: int = 5, tolerance_pct: float = 0.003) -> None:
        """
        Args:
            lookback: number of candles on each side required to confirm a pivot.
            tolerance_pct: fraction of price within which two levels are merged.
        """
        self.lookback = lookback
        self.tolerance_pct = tolerance_pct

    def detect(self, ohlcv: list, window: int = 100) -> SRLevels:
        """Detect S/R levels from the last ``window`` candles.

        Args:
            ohlcv: CCXT-format list [[ts, o, h, l, c, v], ...]
            window: how many recent candles to scan
        """
        candles = ohlcv[-window:] if len(ohlcv) > window else ohlcv
        if len(candles) < self.lookback * 2 + 1:
            return SRLevels(support=None, resistance=None, zones=[])

        highs = np.array([c[2] for c in candles], dtype=float)
        lows = np.array([c[3] for c in candles], dtype=float)
        closes = np.array([c[4] for c in candles], dtype=float)
        current_price = float(closes[-1])

        pivot_highs = self._find_pivots(highs, higher=True)
        pivot_lows = self._find_pivots(lows, higher=False)

        resistance_zones = self._cluster(
            [highs[i] for i in pivot_highs], kind="resistance", ref_price=current_price
        )
        support_zones = self._cluster(
            [lows[i] for i in pivot_lows], kind="support", ref_price=current_price
        )

        all_zones = resistance_zones + support_zones
        all_zones.sort(key=lambda z: z.strength, reverse=True)

        # Nearest support below price and nearest resistance above price
        supports_below = [z for z in support_zones if z.price < current_price]
        resistances_above = [z for z in resistance_zones if z.price > current_price]

        nearest_support = (
            max(supports_below, key=lambda z: z.price).price if supports_below else None
        )
        nearest_resistance = (
            min(resistances_above, key=lambda z: z.price).price if resistances_above else None
        )

        # Fallback when no pivot-based levels are found: use the N-candle price range.
        # This happens in very flat / low-volatility markets where no strict pivot
        # extremes exist.  The range low/high still serve as meaningful S/R proxies.
        if nearest_support is None:
            nearest_support = round(float(lows.min()), 2)
        if nearest_resistance is None:
            nearest_resistance = round(float(highs.max()), 2)

        return SRLevels(
            support=nearest_support,
            resistance=nearest_resistance,
            zones=all_zones[:6],   # top 6 by strength
        )

    def _find_pivots(self, values: np.ndarray, higher: bool) -> list[int]:
        """Return indices of pivot highs (higher=True) or pivot lows (higher=False)."""
        n = len(values)
        pivots = []
        lb = self.lookback
        for i in range(lb, n - lb):
            window = values[i - lb : i + lb + 1]
            if higher and values[i] == window.max() and np.sum(window == values[i]) == 1:
                pivots.append(i)
            elif not higher and values[i] == window.min() and np.sum(window == values[i]) == 1:
                pivots.append(i)
        return pivots

    def _cluster(
        self, levels: list[float], kind: str, ref_price: float
    ) -> list[SRLevel]:
        """Group nearby levels into zones."""
        if not levels:
            return []
        levels_sorted = sorted(levels)
        clusters: list[list[float]] = [[levels_sorted[0]]]
        for price in levels_sorted[1:]:
            tol = clusters[-1][-1] * self.tolerance_pct
            if price - clusters[-1][-1] <= tol:
                clusters[-1].append(price)
            else:
                clusters.append([price])

        result = []
        for cluster in clusters:
            avg = float(np.mean(cluster))
            result.append(
                SRLevel(
                    price=round(avg, 2),
                    kind=kind,
                    strength=len(cluster),
                    last_touch=round(cluster[-1], 2),
                )
            )
        # Sort by strength desc
        result.sort(key=lambda z: z.strength, reverse=True)
        return result[:3]

    @staticmethod
    def fibonacci_levels(swing_low: float, swing_high: float) -> dict:
        """Return Fibonacci retracement levels between a swing low and high.

        Murphy: "Fibonacci levels act as support and resistance in trending markets."

        Returns:
            dict mapping label → price level, e.g. {"0.0%": 40000, "61.8%": 42472, ...}
        """
        diff = swing_high - swing_low
        ratios = {
            "0.0%": 0.0,
            "23.6%": 0.236,
            "38.2%": 0.382,
            "50.0%": 0.500,
            "61.8%": 0.618,
            "78.6%": 0.786,
            "100.0%": 1.0,
        }
        return {label: round(swing_high - diff * ratio, 2) for label, ratio in ratios.items()}
