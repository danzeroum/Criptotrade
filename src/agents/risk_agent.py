"""Risk management agent."""
import json
import os
from typing import Any, Dict
from src.agents.base_agent import BaseAgent
from src.safety.guardrails import GuardrailSystem
import logging

logger = logging.getLogger(__name__)


class RiskAgent(BaseAgent):
    """Validates trades against risk management rules."""

    def __init__(self, llm_client: Any = "auto") -> None:
        super().__init__("risk")
        self.tools = ["portfolio_analyzer", "risk_calculator"]
        self.guardrails = GuardrailSystem()
        # Risk limits read from the environment (config-driven, not hardcoded).
        # Note: cumulative daily-loss enforcement lives at the orchestrator level
        # (CircuitBreaker.DAILY_LOSS_LIMIT_PCT), which has the realised-P&L context
        # the per-order validation here does not — so MAX_DAILY_LOSS_PCT is not read
        # in this agent (it would be a dead, misleading attribute).
        self.max_position_size_pct = self._env_float("MAX_POSITION_SIZE_PCT", 5.0)
        self.stop_loss_pct = self._env_float("STOP_LOSS_PCT", 3.0)
        # Optional LLM for the Reflection step. "auto" → resolve lazily from env;
        # None → disabled; an object → injected (tests). Never raises / can only
        # tighten the decision (advisory).
        self._llm = llm_client

    @staticmethod
    def _env_float(name: str, default: float) -> float:
        try:
            return float(os.getenv(name, str(default)))
        except (TypeError, ValueError):
            return default

    def _resolve_llm(self) -> Any:
        if self._llm == "auto":
            from src.core.llm_client import get_llm_client
            return get_llm_client()
        return self._llm

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Validate trade proposal against risk rules."""
        if not self.validate_input(task):
            raise ValueError("Invalid risk validation task")

        signal = task.get("signal", {})
        portfolio = task.get("portfolio", {})

        # Reflection pattern: validate → reflect → refine
        initial_validation = await self._validate_signal(signal, portfolio)
        reflection = await self._reflect_on_validation(initial_validation, signal)
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

        # Risk guardrails: the GuardrailSystem was instantiated but never invoked,
        # so no order was actually risk-validated. Wire it into the live path here.
        # A violation becomes an issue -> rejection. Never raises (defensive).
        try:
            passed, violations = self.guardrails.validate_order(signal)
        except Exception as exc:  # pragma: no cover - defensive
            passed, violations = False, [f"guardrail error: {exc}"]
        if not passed:
            issues.extend(violations)

        # Check position size
        position_size = signal.get("position_size_pct", 0)
        if position_size > self.max_position_size_pct:
            issues.append(f"Position size {position_size}% exceeds limit {self.max_position_size_pct}%")

        # Pre-trade balance gate: requested notional must not exceed available
        # capital (initial + realised P&L − open exposure). Skipped when the
        # caller supplies no portfolio context (backward compatible).
        available = portfolio.get("available_capital")
        capital_base = portfolio.get("capital_base")
        if available is not None and capital_base:
            try:
                requested = float(capital_base) * float(position_size or 0) / 100.0
                if requested > float(available) + 1e-9:
                    issues.append(
                        f"Insufficient capital: requested notional ${requested:.2f} "
                        f"exceeds available ${float(available):.2f}"
                    )
            except (TypeError, ValueError):  # pragma: no cover - defensive
                pass

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

    async def _reflect_on_validation(
        self, validation: Dict[str, Any], signal: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Reflect on validation to catch edge cases (heuristic + optional LLM)."""
        reflection: Dict[str, Any] = {
            "missed_anything": False,
            "too_strict": False,
            "suggestions": [],
        }

        if validation["approved"] and len(validation["warnings"]) > 2:
            reflection["missed_anything"] = True
            reflection["suggestions"].append("Review warnings for hidden risks")

        # Optional LLM reflection (advisory): may surface hidden risks, never
        # loosens the decision. Best-effort — any failure is ignored.
        llm = self._resolve_llm()
        if llm is not None and signal:
            try:
                await self._llm_reflect(llm, validation, signal, reflection)
            except Exception:  # pragma: no cover - advisory must never break risk
                logger.warning("LLM reflection failed", exc_info=True)

        return reflection

    async def _llm_reflect(
        self,
        llm: Any,
        validation: Dict[str, Any],
        signal: Dict[str, Any],
        reflection: Dict[str, Any],
    ) -> None:
        """Ask the LLM to flag hidden risks. Can only add caution, never approve."""
        system = (
            "You are a conservative crypto risk auditor. Given a proposed order and "
            "its rule-based validation, identify HIDDEN risks not covered by the hard "
            "checks. Respond ONLY with JSON: "
            '{"hidden_risk": <true|false>, "note": "<=200 chars"}.'
        )
        user = json.dumps(
            {
                "signal": {
                    k: signal.get(k)
                    for k in (
                        "action", "entry_price", "stop_loss", "take_profit",
                        "position_size_pct", "regime", "strategy",
                    )
                },
                "validation": {
                    "approved": validation.get("approved"),
                    "issues": validation.get("issues"),
                    "warnings": validation.get("warnings"),
                },
            },
            default=str,
        )
        result = await llm.reason_json(system, user)
        if not result:
            return
        reflection["llm_note"] = result.get("note")
        if result.get("hidden_risk"):
            reflection["missed_anything"] = True
            reflection["suggestions"].append(f"LLM: {result.get('note') or 'hidden risk flagged'}")

    def _refine_validation(self, validation: Dict[str, Any], reflection: Dict[str, Any]) -> Dict[str, Any]:
        """Refine validation based on reflection."""
        final = dict(validation)

        if reflection["missed_anything"]:
            final["confidence"] = min(final["confidence"], 0.75)
            final["requires_review"] = True

        final["refined"] = True
        final["reflection_applied"] = reflection
        return final
