"""Risk management agent."""
from typing import Any, Dict
from src.agents.base_agent import BaseAgent
from src.safety.guardrails import GuardrailSystem
import logging

logger = logging.getLogger(__name__)


class RiskAgent(BaseAgent):
    """Validates trades against risk management rules."""

    def __init__(self) -> None:
        super().__init__("risk")
        self.tools = ["portfolio_analyzer", "risk_calculator"]
        self.guardrails = GuardrailSystem()
        self.max_position_size_pct = 5.0
        self.stop_loss_pct = 3.0
        self.max_daily_loss_pct = 5.0

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Validate trade proposal against risk rules."""
        if not self.validate_input(task):
            raise ValueError("Invalid risk validation task")

        signal = task.get("signal", {})
        portfolio = task.get("portfolio", {})

        # Reflection pattern: validate → reflect → refine
        initial_validation = await self._validate_signal(signal, portfolio)
        reflection = await self._reflect_on_validation(initial_validation)
        final_validation = self._refine_validation(initial_validation, reflection)

        decision = {
            "task": task,
            "initial_validation": initial_validation,
            "reflection": reflection,
            "final_validation": final_validation,
            "confidence": final_validation.get("confidence", 0.0)
        }

        self.log_decision(decision)

        return {
            "success": True,
            "agent": self.agent_type,
            "approved": final_validation["approved"],
            "validation": final_validation,
            "confidence": final_validation.get("confidence", 0.0)
        }

    async def _validate_signal(self, signal: Dict[str, Any], portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """Initial validation."""
        issues = []
        warnings = []

        # Check position size
        position_size = signal.get("position_size_pct", 0)
        if position_size > self.max_position_size_pct:
            issues.append(f"Position size {position_size}% exceeds limit {self.max_position_size_pct}%")

        # Check stop loss
        entry = signal.get("entry_price", 0)
        stop = signal.get("stop_loss", 0)
        if entry > 0:
            stop_loss_pct = abs((stop - entry) / entry * 100)
            if stop_loss_pct > self.stop_loss_pct:
                warnings.append(f"Stop loss {stop_loss_pct:.2f}% is wider than recommended {self.stop_loss_pct}%")

        approved = len(issues) == 0
        confidence = 0.9 if approved else 0.3

        return {
            "approved": approved,
            "issues": issues,
            "warnings": warnings,
            "confidence": confidence
        }

    async def _reflect_on_validation(self, validation: Dict[str, Any]) -> Dict[str, Any]:
        """Reflect on validation to catch edge cases."""
        reflection = {
            "missed_anything": False,
            "too_strict": False,
            "suggestions": []
        }

        if validation["approved"] and len(validation["warnings"]) > 2:
            reflection["missed_anything"] = True
            reflection["suggestions"].append("Review warnings for hidden risks")

        return reflection

    def _refine_validation(self, validation: Dict[str, Any], reflection: Dict[str, Any]) -> Dict[str, Any]:
        """Refine validation based on reflection."""
        final = dict(validation)

        if reflection["missed_anything"]:
            final["confidence"] = min(final["confidence"], 0.75)
            final["requires_review"] = True

        final["refined"] = True
        final["reflection_applied"] = reflection
        return final
