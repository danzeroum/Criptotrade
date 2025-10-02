"""Continuous evaluation utilities for agent trajectories."""

from __future__ import annotations

from typing import Any, Dict


class ContinuousEvaluator:
    def __init__(self, metrics_config: Dict[str, Any]) -> None:
        self.metrics = metrics_config
        self.baseline = None

    def evaluate_trajectory(self, trajectory: Any) -> Dict[str, Any]:
        """Avalia qualidade da trajetória do agente."""

        scores = {
            "task_completion": self.check_goal_achievement(trajectory),
            "efficiency": self.measure_resource_usage(trajectory),
            "safety": self.validate_guardrail_compliance(trajectory),
        }
        return scores

    def check_goal_achievement(self, trajectory: Any) -> float:
        """Placeholder de verificação de objetivos."""

        return 1.0 if getattr(trajectory, "completed", False) else 0.0

    def measure_resource_usage(self, trajectory: Any) -> float:
        """Calcula eficiência baseada em recursos consumidos."""

        used = getattr(trajectory, "resource_usage", 1.0)
        target = self.metrics.get("resource_target", 1.0)
        if target == 0:
            return 0.0
        return max(0.0, min(1.0, target / used))

    def validate_guardrail_compliance(self, trajectory: Any) -> float:
        """Garante que guardrails foram respeitados."""

        violations = getattr(trajectory, "guardrail_violations", 0)
        return 1.0 if violations == 0 else 0.0
