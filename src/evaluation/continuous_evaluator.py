"""Continuous evaluation helpers for agent quality monitoring."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ContinuousEvaluator:
    """Collect rolling metrics for agent executions."""

    metrics: Dict[str, List[float]] = field(
        default_factory=lambda: {
            "task_success_rate": [],
            "average_confidence": [],
            "user_satisfaction": [],
            "error_rate": [],
            "response_time_p95": [],
        }
    )

    async def evaluate_agent_performance(self, agent_name: str, task_result: Dict[str, Any]) -> Dict[str, Any]:
        technical = self.evaluate_technical_quality(task_result)
        business = self.evaluate_business_value(task_result)
        improvement = self.compare_with_baseline(agent_name, task_result)
        summary = {
            "agent": agent_name,
            "technical_score": technical,
            "business_score": business,
            "improvement": improvement,
        }
        self._record("task_success_rate", float(task_result.get("success", 0)))
        self._record("average_confidence", float(task_result.get("confidence", 0)))
        return summary

    def evaluate_technical_quality(self, result: Dict[str, Any]) -> float:
        return float(result.get("technical_score", 0.8))

    def evaluate_business_value(self, result: Dict[str, Any]) -> float:
        return float(result.get("business_score", 0.7))

    def compare_with_baseline(self, agent_name: str, result: Dict[str, Any]) -> float:
        return float(result.get("improvement", 0.0))

    def _record(self, metric: str, value: float) -> None:
        if metric in self.metrics:
            self.metrics[metric].append(value)
