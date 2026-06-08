"""Mean Reversion Strategy.

Buys when the market is oversold (RSI < threshold AND price below Bollinger lower band)
and sells when overbought (RSI > threshold AND price above Bollinger upper band).

The mean the price reverts to is the Bollinger middle band (SMA 20).
Stop loss is placed 2×ATR beyond the entry point.

Douglas / Graham: "Markets oscillate between extremes. The intelligent operator
fades the extreme, not the trend."
"""
from __future__ import annotations

import logging
from typing import Any

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class MeanReversionStrategy(BaseStrategy):
    """Fade extremes using RSI + Bollinger Bands confluence."""

    def __init__(
        self,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        risk_reward_ratio: float = 2.0,
        atr_stop_multiplier: float = 2.0,
    ) -> None:
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.risk_reward = risk_reward_ratio
        self.atr_mult = atr_stop_multiplier

    async def analyze(self, market_data: dict[str, Any]) -> dict[str, Any]:
        """Check for mean reversion entry conditions."""
        indicators = market_data.get("indicators")
        current_price = float(market_data.get("current_price", 0.0))
        regime = market_data.get("regime", "unknown")

        if indicators is None or current_price <= 0:
            return self._hold("no indicator data")

        # Mean reversion works worst in strong trends
        if regime in ("strong_uptrend", "strong_downtrend"):
            return self._hold(f"regime '{regime}' unsuitable for mean reversion")

        rsi = indicators.rsi
        bb_lower = indicators.bb_lower
        bb_upper = indicators.bb_upper
        bb_middle = indicators.bb_middle
        atr = indicators.atr or (current_price * 0.005)   # 0.5% fallback

        # ---- LONG setup: oversold ----
        if (
            rsi is not None and rsi < self.rsi_oversold
            and bb_lower is not None and current_price < bb_lower
        ):
            stop_loss = round(current_price - self.atr_mult * atr, 2)
            risk = current_price - stop_loss
            take_profit = (
                round(bb_middle, 2) if bb_middle
                else round(current_price + self.risk_reward * risk, 2)
            )
            confidence = self._confidence(rsi, "long", indicators)
            return {
                "action": "buy",
                "direction": "long",
                "entry": current_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "position_size_pct": 2.0,
                "confidence": confidence,
                "reason": (
                    f"Mean reversion LONG: RSI={rsi:.1f} < {self.rsi_oversold} "
                    f"and price {current_price:.2f} < BB_lower {bb_lower:.2f}"
                ),
            }

        # ---- SHORT setup: overbought ----
        if (
            rsi is not None and rsi > self.rsi_overbought
            and bb_upper is not None and current_price > bb_upper
        ):
            stop_loss = round(current_price + self.atr_mult * atr, 2)
            risk = stop_loss - current_price
            take_profit = (
                round(bb_middle, 2) if bb_middle
                else round(current_price - self.risk_reward * risk, 2)
            )
            confidence = self._confidence(rsi, "short", indicators)
            return {
                "action": "sell",
                "direction": "short",
                "entry": current_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "position_size_pct": 2.0,
                "confidence": confidence,
                "reason": (
                    f"Mean reversion SHORT: RSI={rsi:.1f} > {self.rsi_overbought} "
                    f"and price {current_price:.2f} > BB_upper {bb_upper:.2f}"
                ),
            }

        return self._hold(
            f"No mean reversion signal (RSI={rsi:.1f if rsi else 'N/A'}, "
            f"price {'below' if bb_lower and current_price < bb_lower else 'within'} bands)"
        )

    def _confidence(
        self, rsi: float | None, direction: str, indicators: Any
    ) -> float:
        score = 0.60   # base: two conditions already confirmed (RSI + BB)

        if rsi is not None:
            # Deeper extreme → higher confidence
            if direction == "long":
                overshoot = max(0.0, self.rsi_oversold - rsi)
                score += min(overshoot / 30.0, 0.20)
            else:
                overshoot = max(0.0, rsi - self.rsi_overbought)
                score += min(overshoot / 30.0, 0.20)

        # Volume spike confirms institutional participation
        vol_ratio = indicators.volume_ratio if indicators else None
        if vol_ratio and vol_ratio > 1.5:
            score += 0.10

        # Stochastic confirmation
        if indicators:
            k = indicators.stochastic_k
            if direction == "long" and k is not None and k < 20:
                score += 0.10
            elif direction == "short" and k is not None and k > 80:
                score += 0.10

        return min(round(score, 4), 0.92)

    @staticmethod
    def _hold(reason: str) -> dict[str, Any]:
        return {"action": "hold", "confidence": 0.05, "reason": reason}

    def get_parameters(self) -> dict[str, Any]:
        return {
            "name": "Mean Reversion",
            "risk_profile": "medium",
            "rsi_oversold": self.rsi_oversold,
            "rsi_overbought": self.rsi_overbought,
            "risk_reward_ratio": self.risk_reward,
            "atr_stop_multiplier": self.atr_mult,
            "suitable_for": "sideways markets, range-bound assets",
        }
