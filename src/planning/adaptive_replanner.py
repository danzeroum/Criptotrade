"""Adaptive planner capable of recovering from failures."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class AdaptivePlanner:
    """Execute plans with the ability to replan after failures."""

    max_replanning_attempts: int = 3
    failure_history: List[Dict[str, Any]] = field(default_factory=list)

    async def execute_with_replanning(self, initial_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Attempt to execute a plan with limited replanning attempts."""

        plan = dict(initial_plan)
        for attempt in range(1, self.max_replanning_attempts + 1):
            result = await self._execute_plan(plan)
            if result.get("success", False):
                return {"plan": plan, "result": result, "attempts": attempt}

            failure_context = self._analyze_failure(result, plan)
            self.failure_history.append(failure_context)
            plan = self._create_recovery_plan(initial_plan, failure_context)
        return {"plan": plan, "result": {"success": False}, "attempts": self.max_replanning_attempts}

    async def _execute_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        await asyncio.sleep(0)
        if not plan.get("steps"):
            return {"success": True, "details": "Plano trivial executado"}
        return {"success": True, "details": "Plano executado"}

    def _analyze_failure(self, result: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "plan": plan,
            "result": result,
            "reason": result.get("error", "unknown"),
        }

    def _create_recovery_plan(self, original_plan: Dict[str, Any], failure: Dict[str, Any]) -> Dict[str, Any]:
        new_plan = dict(original_plan)
        new_plan.setdefault("recovery", []).append({"from": failure})
        return new_plan
