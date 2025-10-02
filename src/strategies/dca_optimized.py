"""DCA (Dollar Cost Averaging) Optimized Strategy."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import logging

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class DCAOptimizedStrategy(BaseStrategy):
    """Dollar Cost Averaging strategy with optimisation for crypto markets."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.position_size_pct = self.config.get("position_size_pct", 2.0)
        self.num_entries = self.config.get("num_entries", 3)
        self.spacing_pct = self.config.get("spacing_pct", 1.0)
        self.stop_loss_pct = self.config.get("stop_loss_pct", 3.0)
        self.rsi_oversold = self.config.get("rsi_oversold", 35)
        self.min_volume_ratio = self.config.get("min_volume_ratio", 0.8)

        logger.info(
            "DCA strategy initialised",
            extra={
                "entries": self.num_entries,
                "position_size_pct": self.position_size_pct,
                "spacing_pct": self.spacing_pct,
            },
        )

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        symbol = market_data.get("symbol", "UNKNOWN")
        current_price = market_data.get("current_price", 0.0)

        logger.info("[DCA] Analyzing", extra={"symbol": symbol, "price": current_price})

        trend = self._analyze_trend(market_data)
        indicators = self._check_indicators(market_data)
        volume_ok = self._check_volume(market_data)

        if self._should_enter(trend, indicators, volume_ok):
            signal = self._generate_entry_signal(market_data)
            confidence = self._calculate_confidence(trend, indicators, volume_ok)
            return {
                "action": "DCA_ENTRY",
                "signal": signal,
                "confidence": confidence,
                "reasoning": self._explain_reasoning(trend, indicators, volume_ok),
            }

        return {
            "action": "WAIT",
            "signal": None,
            "confidence": 0.0,
            "reasoning": "Conditions not met for DCA entry",
        }

    def _analyze_trend(self, market_data: Dict[str, Any]) -> str:
        ma_20 = market_data.get("ma_20", 0)
        ma_50 = market_data.get("ma_50", 0)
        current_price = market_data.get("current_price", 0)

        if current_price < ma_20 < ma_50:
            return "downtrend"
        if ma_50 and abs(ma_20 - ma_50) / ma_50 < 0.02:
            return "sideways"
        return "uptrend"

    def _check_indicators(self, market_data: Dict[str, Any]) -> Dict[str, bool]:
        rsi = market_data.get("rsi", 50)
        macd_histogram = market_data.get("macd_histogram", 0)

        return {
            "rsi_oversold": rsi < self.rsi_oversold,
            "macd_positive_divergence": macd_histogram > 0,
            "bollinger_lower": market_data.get("at_bollinger_lower", False),
        }

    def _check_volume(self, market_data: Dict[str, Any]) -> bool:
        current_volume = market_data.get("volume_24h", 0)
        avg_volume = market_data.get("avg_volume", 1)
        if avg_volume == 0:
            return False
        return (current_volume / avg_volume) >= self.min_volume_ratio

    def _should_enter(
        self,
        trend: str,
        indicators: Dict[str, bool],
        volume_ok: bool,
    ) -> bool:
        trend_ok = trend in {"downtrend", "sideways"}
        indicators_confirmed = sum(indicators.values()) >= 2
        return trend_ok and indicators_confirmed and volume_ok

    def _generate_entry_signal(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        symbol = market_data.get("symbol")
        current_price = market_data.get("current_price", 0.0)

        entries = []
        for index in range(self.num_entries):
            entry_price = current_price * (1 - (index * self.spacing_pct / 100))
            entries.append(
                {
                    "entry_number": index + 1,
                    "price": round(entry_price, 2),
                    "size_pct": self.position_size_pct,
                }
            )

        avg_entry = sum(entry["price"] for entry in entries) / len(entries)
        stop_loss_price = avg_entry * (1 - self.stop_loss_pct / 100)
        risk = avg_entry - stop_loss_price
        take_profit_price = avg_entry + (3 * risk)

        signal = {
            "symbol": symbol,
            "strategy": "DCA_OPTIMIZED",
            "action": "BUY",
            "entries": entries,
            "avg_entry_price": round(avg_entry, 2),
            "stop_loss": round(stop_loss_price, 2),
            "take_profit": round(take_profit_price, 2),
            "total_position_size_pct": self.position_size_pct * self.num_entries,
            "risk_reward_ratio": 3.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info("[DCA] Signal generated", extra=signal)
        return signal

    def _calculate_confidence(
        self,
        trend: str,
        indicators: Dict[str, bool],
        volume_ok: bool,
    ) -> float:
        score = 0.5
        if trend == "downtrend":
            score += 0.15
        elif trend == "sideways":
            score += 0.10

        score += (sum(indicators.values()) / max(len(indicators), 1)) * 0.25

        if volume_ok:
            score += 0.10

        return min(score, 1.0)

    def _explain_reasoning(
        self,
        trend: str,
        indicators: Dict[str, bool],
        volume_ok: bool,
    ) -> str:
        reasoning = [f"Market trend: {trend}"]
        confirmed = [name for name, value in indicators.items() if value]
        if confirmed:
            reasoning.append(f"Confirmed indicators: {', '.join(confirmed)}")
        reasoning.append(f"Volume adequate: {volume_ok}")
        reasoning.append(
            f"DCA approach with {self.num_entries} entries at {self.spacing_pct}% spacing reduces timing risk"
        )
        return " | ".join(reasoning)

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "name": "DCA Optimized",
            "risk_profile": "low",
            "position_size_pct": self.position_size_pct,
            "num_entries": self.num_entries,
            "spacing_pct": self.spacing_pct,
            "stop_loss_pct": self.stop_loss_pct,
            "suitable_for": "long-term accumulation, bear markets",
        }
