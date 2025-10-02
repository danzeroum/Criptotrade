"""Auditor agent providing reflective quality and security assessments."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
import logging

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AuditorAgent(BaseAgent):
    """Security and quality specialist with reflection capabilities."""

    def __init__(self) -> None:
        super().__init__("auditor")
        self.validation_history: List[Dict[str, Any]] = []
        self.tools = ["security_scan", "quality_check"]

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        if not self.validate_input(task):
            raise ValueError("Invalid audit task payload")

        initial = await self.audit(task)
        reflection = await self.reflect_on_assessment(initial)
        final = self.refine_assessment(initial, reflection)
        final.update({"timestamp": datetime.now(timezone.utc).isoformat()})

        self.validation_history.append(final)
        self.log_decision({"task": task, "assessment": final, "confidence": final.get("confidence", 0.0)})
        return {
            "success": True,
            "agent": self.agent_type,
            "initial": initial,
            "reflection": reflection,
            "final": final,
            "confidence": final.get("confidence", 0.0),
        }

    async def audit(self, task: Dict[str, Any]) -> Dict[str, Any]:
        issues: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        code = task.get("code")
        if code:
            issues.extend(self.check_security(code))
        metrics = task.get("metrics")
        if metrics:
            warnings.extend(self.check_quality(metrics))

        passed = not issues
        confidence = 0.9 if passed else 0.7
        return {"issues": issues, "warnings": warnings, "passed": passed, "confidence": confidence}

    async def reflect_on_assessment(self, assessment: Dict[str, Any]) -> Dict[str, Any]:
        reflection = {
            "missed_anything": False,
            "too_strict": False,
            "suggestions": [],
        }
        if assessment["passed"] and assessment.get("confidence", 0) < 0.8:
            reflection["missed_anything"] = True
            reflection["suggestions"].append("Expand coverage for edge cases")
        if len(assessment.get("warnings", [])) > 5:
            reflection["too_strict"] = True
            reflection["suggestions"].append("Focus on critical issues")
        return reflection

    def refine_assessment(self, assessment: Dict[str, Any], reflection: Dict[str, Any]) -> Dict[str, Any]:
        final = dict(assessment)
        if reflection["missed_anything"]:
            final.setdefault("additional_checks", []).extend(["edge_cases", "performance", "scalability"])
            final["confidence"] = min(final.get("confidence", 0.7), 0.75)
        if reflection["too_strict"]:
            final["issues"] = [issue for issue in final["issues"] if issue.get("severity") == "critical"]
        final["refined"] = True
        final["reflection_applied"] = reflection
        return final

    def check_security(self, code: str) -> List[Dict[str, Any]]:
        dangerous_patterns = [
            ("eval(", "Code injection risk"),
            ("exec(", "Code execution risk"),
            ("__import__", "Dynamic import risk"),
            ("os.system", "System command execution"),
            ("subprocess", "Process spawning risk"),
        ]
        issues: List[Dict[str, Any]] = []
        for pattern, description in dangerous_patterns:
            if pattern in code:
                issues.append({
                    "type": "security",
                    "severity": "critical",
                    "pattern": pattern,
                    "description": description,
                })
        return issues

    def check_quality(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        warnings: List[Dict[str, Any]] = []
        complexity = metrics.get("complexity")
        if complexity is not None and complexity > 10:
            warnings.append({
                "type": "quality",
                "severity": "warning",
                "metric": "complexity",
                "value": complexity,
                "threshold": 10,
            })
        coverage = metrics.get("coverage")
        if coverage is not None and coverage < 80:
            warnings.append({
                "type": "quality",
                "severity": "warning",
                "metric": "coverage",
                "value": coverage,
                "threshold": 80,
            })
        return warnings

    async def validate_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        scores: Dict[str, float] = {}
        issues: List[str] = []
        for result in results:
            agent_name = result.get("agent", "unknown")
            score = self.score_agent_result(result)
            scores[agent_name] = score
            if score < 0.6:
                issues.append(f"Low quality from {agent_name}: {score:.2f}")
        approved = not issues
        confidence = sum(scores.values()) / len(scores) if scores else 0.0
        return {"approved": approved, "confidence": confidence, "issues": issues, "agent_scores": scores}

    def score_agent_result(self, result: Dict[str, Any]) -> float:
        score = 0.5
        if result.get("success"):
            score += 0.2
        if result.get("confidence", 0) > 0.7:
            score += 0.1
        if "error" not in result:
            score += 0.1
        if result.get("tested"):
            score += 0.1
        return min(score, 1.0)
