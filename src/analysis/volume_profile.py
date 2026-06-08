"""Volume Profile analysis.

POC (Point of Control): price level with the highest traded volume.
Value Area: price range containing 70% of all traded volume.
LVN (Low Volume Nodes): price levels with unusually low volume (gaps).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class VolumeProfileResult:
    """Result of a volume profile analysis."""
    poc: float                          # Point of Control price
    value_area_high: float             # Top of 70% value area
    value_area_low: float              # Bottom of 70% value area
    low_volume_nodes: list[float] = field(default_factory=list)   # LVN prices


class VolumeProfile:
    """Compute volume distribution across price bins.

    A high-volume node (HVN) / POC signals strong consensus at that price.
    A low-volume node (LVN) signals a price gap — moves through LVNs tend to be fast.
    """

    def __init__(self, ohlcv: list, price_bins: int = 20) -> None:
        """
        Args:
            ohlcv: CCXT-format list [[ts, o, h, l, c, v], ...]
            price_bins: number of price buckets for the profile.
        """
        self._ohlcv = ohlcv
        self._bins = price_bins

    def analyze(self) -> VolumeProfileResult:
        """Build the volume profile and return key levels."""
        if len(self._ohlcv) < 2:
            # Not enough data — return midpoint of the single candle
            price = float(self._ohlcv[0][4]) if self._ohlcv else 0.0
            return VolumeProfileResult(poc=price, value_area_high=price, value_area_low=price)

        closes = np.array([c[4] for c in self._ohlcv], dtype=float)
        highs = np.array([c[2] for c in self._ohlcv], dtype=float)
        lows = np.array([c[3] for c in self._ohlcv], dtype=float)

        price_min = float(lows.min())
        price_max = float(highs.max())

        if price_max <= price_min:
            poc = float(closes.mean())
            return VolumeProfileResult(poc=poc, value_area_high=poc, value_area_low=poc)

        edges = np.linspace(price_min, price_max, self._bins + 1)
        bin_volume = np.zeros(self._bins)

        for i, c in enumerate(self._ohlcv):
            close = float(c[4])
            vol = float(c[5])
            # Assign candle volume to the bin containing its close price
            idx = int(np.digitize(close, edges) - 1)
            idx = max(0, min(idx, self._bins - 1))
            bin_volume[idx] += vol

        # POC = bin with maximum volume
        poc_bin = int(np.argmax(bin_volume))
        poc_price = float((edges[poc_bin] + edges[poc_bin + 1]) / 2)

        # Value Area: accumulate 70% of total volume starting from POC outward
        total_vol = float(bin_volume.sum())
        if total_vol == 0:
            return VolumeProfileResult(
                poc=poc_price, value_area_high=poc_price, value_area_low=poc_price
            )

        target = 0.70 * total_vol
        accumulated = float(bin_volume[poc_bin])
        lo_idx = poc_bin
        hi_idx = poc_bin

        while accumulated < target:
            can_go_lower = lo_idx > 0
            can_go_higher = hi_idx < self._bins - 1
            if not can_go_lower and not can_go_higher:
                break
            next_lo = bin_volume[lo_idx - 1] if can_go_lower else -1.0
            next_hi = bin_volume[hi_idx + 1] if can_go_higher else -1.0
            if next_hi >= next_lo:
                hi_idx += 1
                accumulated += bin_volume[hi_idx]
            else:
                lo_idx -= 1
                accumulated += bin_volume[lo_idx]

        vah = float((edges[hi_idx] + edges[hi_idx + 1]) / 2)
        val = float((edges[lo_idx] + edges[lo_idx + 1]) / 2)

        # LVN = bins with volume below 30% of the average bin volume
        avg_vol_per_bin = total_vol / self._bins
        lvn_prices = [
            float((edges[i] + edges[i + 1]) / 2)
            for i in range(self._bins)
            if bin_volume[i] < 0.3 * avg_vol_per_bin
        ]

        return VolumeProfileResult(
            poc=round(poc_price, 2),
            value_area_high=round(vah, 2),
            value_area_low=round(val, 2),
            low_volume_nodes=[round(p, 2) for p in lvn_prices[:5]],
        )
