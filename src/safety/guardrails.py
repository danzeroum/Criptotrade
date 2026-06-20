"""Guardrail system for order validation."""
from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


def _max_position_size_pct() -> float:
    """Max position size (% of capital) from ``MAX_POSITION_SIZE_PCT`` env (default 5.0)."""
    try:
        return float(os.getenv("MAX_POSITION_SIZE_PCT", "5.0"))
    except (TypeError, ValueError):
        return 5.0


Guardrail = Callable[[dict[str, Any]], tuple[bool, str]]
# Sink called once per violation message. Kept as a plain str callback so this
# module stays decoupled from the alert types (the wiring builds the Alert).
AlertSink = Callable[[str], None]


@dataclass
class GuardrailSystem:
    """Collection of guardrails for trade validation."""

    rules: list[Guardrail] = field(default_factory=list)
    # Optional in-process sink: every violation is published (e.g. persisted to
    # the AlertStore so it shows in /v1/alerts). None = log only (current default).
    alert_sink: AlertSink | None = None

    def __post_init__(self) -> None:
        if not self.rules:
            self.rules = [
                self.check_position_size,
                self.check_stop_loss,
                self.check_risk_reward,
                self.check_market_conditions,
            ]

    def validate_order(self, order: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate order against all guardrails."""
        violations: list[str] = []

        for rule in self.rules:
            passed, message = rule(order)
            if not passed and message:
                violations.append(message)
                logger.warning("Guardrail violation: %s", message)
                if self.alert_sink is not None:
                    try:
                        self.alert_sink(message)
                    except Exception:  # pragma: no cover - sink must never break validation
                        logger.exception("alert_sink failed for: %s", message)

        return len(violations) == 0, violations

    def check_position_size(self, order: dict[str, Any]) -> tuple[bool, str]:
        """Validate position size."""
        max_size = _max_position_size_pct()
        position_size = order.get("position_size_pct", 0)

        if position_size > max_size:
            return False, f"Position size {position_size}% exceeds maximum {max_size}%"

        return True, ""

    def check_stop_loss(self, order: dict[str, Any]) -> tuple[bool, str]:
        """Validate stop loss is present."""
        if "stop_loss" not in order or order["stop_loss"] is None:
            return False, "Stop loss is mandatory"

        entry = order.get("entry_price") or 0
        stop = order["stop_loss"]

        if entry > 0:
            action = order.get("action", "").upper()
            if action == "BUY" and stop >= entry:
                return False, "Stop loss must be below entry for BUY orders"
            if action == "SELL" and stop <= entry:
                return False, "Stop loss must be above entry for SELL orders"

        return True, ""

    def check_risk_reward(self, order: dict[str, Any]) -> tuple[bool, str]:
        """Validate risk-reward ratio.

        Grid and other strategies may omit take_profit (None) when exits are managed
        level-by-level. In those cases the RR check is skipped.
        """
        entry = order.get("entry_price") or 0
        stop = order.get("stop_loss") or 0
        target = order.get("take_profit") or 0

        if entry > 0 and stop > 0 and target > 0:
            risk = abs(entry - stop)
            reward = abs(target - entry)
            min_ratio = 2.5

            if risk > 0:
                ratio = reward / risk
                if ratio < min_ratio:
                    return False, f"Risk-reward ratio {ratio:.2f} is below minimum {min_ratio}"

        return True, ""

    def check_market_conditions(self, order: dict[str, Any]) -> tuple[bool, str]:
        """Reject orders when market conditions make trading unsafe.

        Reads optional ``market_context`` dict attached to the order by the
        StrategyAgent. When absent the check is a no-op (fail-open for backward
        compatibility with callers that don't supply context).

        Rejects when:
          - atr / bb_middle > 0.10  (extreme intrabar volatility)
          - volume_ratio < 0.3      (dangerously thin liquidity)
        """
        ctx = order.get("market_context")
        if not ctx:
            return True, ""

        atr = ctx.get("atr")
        bb_middle = ctx.get("bb_middle")
        volume_ratio = ctx.get("volume_ratio")

        if atr is not None and bb_middle is not None and bb_middle > 0:
            volatility_pct = atr / bb_middle
            if volatility_pct > 0.10:
                return False, (
                    f"Extreme volatility (ATR/BB_mid={volatility_pct:.2%}) exceeds 10% threshold"
                )

        if volume_ratio is not None and volume_ratio < 0.3:
            return False, (
                f"Insufficient liquidity (volume_ratio={volume_ratio:.2f} < 0.3)"
            )

        return True, ""
