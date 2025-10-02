"""Adaptive planner capable of replanning when failures occur."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
import logging
import uuid

logger = logging.getLogger(__name__)


class AdaptivePlanner:
    """Create adaptive plans and support recovery when steps fail."""

    def __init__(self) -> None:
        self.plan_history: List[Dict[str, Any]] = []
        self.max_replanning_attempts = 3
        self.failure_patterns: Dict[str, int] = {}

    async def create_adaptive_plan(self, task: Dict[str, Any]) -> Dict[str, Any]:
        plan = {
            "plan_id": str(uuid.uuid4()),
            "task_id": task.get("task_id", str(uuid.uuid4())),
            "goal": task.get("description", ""),
            "steps": await self._decompose_task(task),
            "estimated_duration": self._estimate_duration(task),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "adaptive": True,
        }
        plan["confidence"] = self._calculate_plan_confidence(plan)
        self.plan_history.append(plan)
        return plan

    async def _decompose_task(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        steps: List[Dict[str, Any]] = []
        steps.append(
            {
                "step": 1,
                "action": "analyze",
                "description": "Analyze requirements and constraints",
                "estimated_time": 5,
                "dependencies": [],
                "can_fail": True,
            }
        )
        if task.get("priority") == "high":
            steps.append(
                {
                    "step": 2,
                    "action": "design",
                    "description": "Produce detailed design",
                    "estimated_time": 15,
                    "dependencies": [1],
                    "can_fail": True,
                }
            )
        steps.append(
            {
                "step": len(steps) + 1,
                "action": "implement",
                "description": "Implement solution",
                "estimated_time": 30,
                "dependencies": [steps[-1]["step"]],
                "can_fail": True,
            }
        )
        steps.append(
            {
                "step": len(steps) + 1,
                "action": "validate",
                "description": "Validate and test",
                "estimated_time": 10,
                "dependencies": [steps[-1]["step"]],
                "can_fail": False,
            }
        )
        return steps

    def _estimate_duration(self, task: Dict[str, Any]) -> int:
        base = 60
        if task.get("priority") == "high":
            base = int(base * 1.5)
        if task.get("complexity") == "high":
            base = int(base * 2)
        return base

    def _calculate_plan_confidence(self, plan: Dict[str, Any]) -> float:
        confidence = 0.8
        if len(plan["steps"]) > 5:
            confidence -= 0.1
        if plan.get("estimated_duration", 0) > 120:
            confidence -= 0.1
        return max(0.3, confidence)

    async def replan_from_point(self, original_plan: Dict[str, Any], failed_step: Dict[str, Any], reflection: Dict[str, Any]) -> Dict[str, Any]:
        failure_key = f"{failed_step.get('action')}_{reflection.get('reason', 'unknown')}"
        self.failure_patterns[failure_key] = self.failure_patterns.get(failure_key, 0) + 1

        new_plan = dict(original_plan)
        new_plan["plan_id"] = str(uuid.uuid4())
        new_plan["replanned"] = True
        new_plan["replanning_reason"] = reflection
        new_plan["parent_plan"] = original_plan.get("plan_id")

        completed = [step for step in original_plan["steps"] if step["step"] < failed_step["step"]]
        recovery_steps = await self._create_recovery_steps(failed_step, reflection)
        remaining = [step for step in original_plan["steps"] if step["step"] > failed_step["step"]]

        reordered: List[Dict[str, Any]] = []
        reordered.extend(completed)
        reordered.extend(recovery_steps)
        for index, step in enumerate(remaining, start=len(reordered) + 1):
            step = dict(step)
            step["step"] = index
            step["dependencies"] = [index - 1] if index > 1 else []
            reordered.append(step)

        new_plan["steps"] = reordered
        new_plan["confidence"] = self._calculate_plan_confidence(new_plan) * 0.9
        self.plan_history.append(new_plan)
        return new_plan

    async def _create_recovery_steps(self, failed_step: Dict[str, Any], reflection: Dict[str, Any]) -> List[Dict[str, Any]]:
        steps: List[Dict[str, Any]] = []
        steps.append(
            {
                "step": failed_step["step"],
                "action": "diagnose",
                "description": f"Diagnose failure in {failed_step['action']}",
                "estimated_time": 5,
                "dependencies": [],
                "recovery": True,
            }
        )
        steps.append(
            {
                "step": failed_step["step"] + 1,
                "action": "fix",
                "description": f"Apply fix for {reflection.get('reason', 'issue')}",
                "estimated_time": 10,
                "dependencies": [failed_step["step"]],
                "recovery": True,
            }
        )
        retry_step = dict(failed_step)
        retry_step["step"] = failed_step["step"] + 2
        retry_step["description"] = f"Retry: {failed_step['description']}"
        retry_step["dependencies"] = [failed_step["step"] + 1]
        retry_step["retry"] = True
        steps.append(retry_step)
        return steps

    def analyze_failure(self, error: Exception, plan: Dict[str, Any]) -> Dict[str, Any]:
        message = str(error)
        reason = "unknown"
        suggestion = "investigate"
        lowered = message.lower()
        if "timeout" in lowered:
            reason, suggestion = "timeout", "increase_timeout"
        elif "memory" in lowered:
            reason, suggestion = "memory_limit", "optimise_memory"
        return {
            "error_type": type(error).__name__,
            "error_message": message,
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "plan_id": plan.get("plan_id"),
            "reason": reason,
            "suggestion": suggestion,
        }
