"""Progressive autonomy manager for Human-in-the-loop workflows."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class ProgressiveAutonomyManager:
    """Track trust scores and autonomy levels for agents."""

    autonomy_levels: Dict[int, str] = field(
        default_factory=lambda: {
            0: "full_human_control",
            1: "human_approval_critical",
            2: "human_notification",
            3: "full_autonomy",
        }
    )
    agent_trust_scores: Dict[str, float] = field(default_factory=dict)
    action_history: List[Dict[str, Any]] = field(default_factory=list)

    def _get_autonomy_level(self, agent: str) -> int:
        score = self.agent_trust_scores.get(agent, 0.5)
        if score < 0.4:
            return 0
        if score < 0.6:
            return 1
        if score < 0.8:
            return 2
        return 3

    async def execute_with_autonomy(self, agent: str, action: Dict[str, Any]) -> Dict[str, Any]:
        critical = action.get("critical", False)
        needs_approval = self._needs_human_approval(agent, critical)
        if needs_approval:
            approval = await self._request_human_approval(agent, action)
            if not approval.get("approved", False):
                self.record_action(agent, action, success=False)
                return {"executed": False, "reason": "Rejected by human", "feedback": approval.get("feedback")}
            modifications = approval.get("modifications")
            if modifications:
                action = {**action, **modifications}
        result = await self._execute_action(action)
        self.record_action(agent, action, success=result.get("success", False))
        self._adjust_autonomy_level(agent)
        return {"executed": True, **result}

    def record_action(self, agent: str, action: Dict[str, Any], success: bool) -> None:
        current_level = self._get_autonomy_level(agent)
        self.agent_trust_scores[agent] = self._update_score(agent, success)
        self.action_history.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": agent,
                "action": action,
                "success": success,
                "trust_score": self.agent_trust_scores[agent],
                "autonomy_level": current_level,
            }
        )

    def _update_score(self, agent: str, success: bool) -> float:
        score = self.agent_trust_scores.get(agent, 0.5)
        if success:
            score = min(1.0, score + 0.02)
        else:
            score = max(0.0, score - 0.1)
        self.agent_trust_scores[agent] = score
        return score

    def _needs_human_approval(self, agent: str, critical: bool) -> bool:
        level = self._get_autonomy_level(agent)
        if level == 3:
            return False
        if level == 2:
            return critical
        return True

    async def _request_human_approval(self, agent: str, action: Dict[str, Any]) -> Dict[str, Any]:
        # Placeholder for real approval workflow; assume approved with no modifications
        return {"approved": True, "modifications": None, "feedback": None}

    async def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        # Placeholder for actual execution logic
        return {"success": True, "action": action}

    def _adjust_autonomy_level(self, agent: str) -> None:
        # Autonomy is derived from trust score; nothing additional required here
        pass

    def needs_human_approval(self, agent: str, critical: bool) -> bool:
        return self._needs_human_approval(agent, critical)
