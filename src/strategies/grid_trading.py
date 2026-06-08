"""Grid Trading Strategy.

Places buy orders at regular price levels below the current price and sell orders
above it. Profits from small oscillations in sideways markets.

Activation condition: regime == "sideways" (EMA spread < 2%).
Direction bias: long if price < POC (Volume Profile), short if price > POC.

Murphy: "Markets spend 70-80% of their time in trading ranges."
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class GridTradingStrategy(BaseStrategy):
    """Dollar-neutral grid strategy for consolidating markets."""

    def __init__(
        self,
        grid_levels: int = 10,
        grid_spacing_pct: float = 1.0,
        total_size_pct: float = 10.0,
    ) -> None:
        """
        Args:
            grid_levels: number of grid levels on each side.
            grid_spacing_pct: percentage distance between grid levels.
            total_size_pct: total portfolio percentage allocated to the grid.
        """
        self.grid_levels = grid_levels
        self.grid_spacing_pct = grid_spacing_pct / 100.0
        self.total_size_pct = total_size_pct / 100.0
        self.size_per_level = self.total_size_pct / (grid_levels * 2)

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a grid setup signal if market conditions are suitable."""
        indicators = market_data.get("indicators")
        current_price = float(market_data.get("current_price", 0.0))
        regime = market_data.get("regime", "unknown")

        if current_price <= 0:
            return self._hold("current price unavailable")

        # Only activate in sideways markets
        if regime not in ("sideways", "unknown"):
            return self._hold(f"regime '{regime}' not suitable for grid trading")

        # Check EMA spread as a secondary confirmation
        if indicators:
            ema_fast = indicators.ema_fast
            ema_slow = indicators.ema_slow
            if ema_fast and ema_slow:
                ema_spread = abs(ema_fast - ema_slow) / current_price
                if ema_spread > 0.02:
                    return self._hold(f"EMA spread {ema_spread:.1%} too wide for grid")

        # Determine directional bias from Volume Profile POC
        vp = market_data.get("volume_profile")
        direction: Optional[str] = None
        if vp and vp.poc:
            direction = "long" if current_price < vp.poc else "short"
        else:
            direction = "long"   # default to long if no VP data

        # Build grid levels
        buy_levels, sell_levels = self._build_grid(current_price)

        # Calculate stop based on grid extremes
        grid_low = min(buy_levels)
        grid_high = max(sell_levels)
        if direction == "long":
            stop_loss = round(grid_low * (1 - self.grid_spacing_pct * 2), 2)
        else:
            stop_loss = round(grid_high * (1 + self.grid_spacing_pct * 2), 2)

        action = "buy" if direction == "long" else "sell"
        confidence = self._confidence(indicators)

        return {
            "action": action,
            "direction": direction,
            "entry": current_price,
            "stop_loss": stop_loss,
            "take_profit": None,   # grid manages exits level by level
            "position_size_pct": self.size_per_level * 100,
            "total_position_size_pct": self.total_size_pct * 100,
            "grid_levels": {
                "buy": buy_levels,
                "sell": sell_levels,
            },
            "confidence": confidence,
            "reason": (
                f"Grid setup in {regime} market, direction={direction}, "
                f"POC={vp.poc if vp else 'N/A'}"
            ),
        }

    def _build_grid(self, center: float) -> tuple[List[float], List[float]]:
        """Return sorted lists of buy and sell grid prices around center."""
        buy_levels = [
            round(center * (1 - (i + 1) * self.grid_spacing_pct), 2)
            for i in range(self.grid_levels)
        ]
        sell_levels = [
            round(center * (1 + (i + 1) * self.grid_spacing_pct), 2)
            for i in range(self.grid_levels)
        ]
        return sorted(buy_levels), sorted(sell_levels)

    @staticmethod
    def _confidence(indicators: Any) -> float:
        score = 0.50
        if indicators:
            # Low volatility → more suitable for grid
            if indicators.atr and indicators.bb_middle:
                vol_pct = indicators.atr / indicators.bb_middle
                if vol_pct < 0.01:
                    score += 0.20
                elif vol_pct < 0.02:
                    score += 0.10
            # Volume near average → stable participation
            if indicators.volume_ratio and 0.7 < indicators.volume_ratio < 1.5:
                score += 0.15
        return min(score, 0.85)

    @staticmethod
    def _hold(reason: str) -> Dict[str, Any]:
        return {"action": "hold", "confidence": 0.05, "reason": reason}

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "name": "Grid Trading",
            "risk_profile": "medium",
            "grid_levels": self.grid_levels,
            "grid_spacing_pct": self.grid_spacing_pct * 100,
            "total_size_pct": self.total_size_pct * 100,
            "suitable_for": "sideways, low-volatility markets",
        }
