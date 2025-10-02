"""Guardrail system for order validation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

Guardrail = Callable[[Dict[str, Any]], Tuple[bool, str]]


@dataclass
class GuardrailSystem:
    """Collection of guardrails for trade validation."""

    rules: List[Guardrail] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.rules:
            self.rules = [
                self.check_position_size,
                self.check_stop_loss,
                self.check_risk_reward,
                self.check_market_conditions,
            ]

    def validate_order(self, order: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate order against all guardrails."""
        violations: List[str] = []

        for rule in self.rules:
            passed, message = rule(order)
            if not passed and message:
                violations.append(message)
                logger.warning("Guardrail violation: %s", message)

        return len(violations) == 0, violations

    def check_position_size(self, order: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate position size."""
        max_size = 5.0
        position_size = order.get("position_size_pct", 0)

        if position_size > max_size:
            return False, f"Position size {position_size}% exceeds maximum {max_size}%"

        return True, ""

    def check_stop_loss(self, order: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate stop loss is present."""
        if "stop_loss" not in order or order["stop_loss"] is None:
            return False, "Stop loss is mandatory"

        entry = order.get("entry_price", 0)
        stop = order["stop_loss"]

        if entry > 0:
            action = order.get("action", "").upper()
            if action == "BUY" and stop >= entry:
                return False, "Stop loss must be below entry for BUY orders"
            if action == "SELL" and stop <= entry:
                return False, "Stop loss must be above entry for SELL orders"

        return True, ""

    def check_risk_reward(self, order: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate risk-reward ratio."""
        entry = order.get("entry_price", 0)
        stop = order.get("stop_loss", 0)
        target = order.get("take_profit", 0)

        if entry > 0 and stop > 0 and target > 0:
            risk = abs(entry - stop)
            reward = abs(target - entry)
            min_ratio = 2.5

            if risk > 0:
                ratio = reward / risk
                if ratio < min_ratio:
                    return False, f"Risk-reward ratio {ratio:.2f} is below minimum {min_ratio}"

        return True, ""

    def check_market_conditions(self, order: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if market conditions are suitable."""
        # TODO: Implement market condition checks
        return True, ""
