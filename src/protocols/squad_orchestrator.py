"""Cooperative orchestration between BuildToValue agents."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from src.agents.architect_agent import ArchitectAgent
from src.agents.developer_agent import DeveloperAgent


@dataclass
class A2ASquad:
    """Coordinate tasks between multiple specialised agents (agent-to-agent).

    Renamed from ``SquadOrchestrator`` to disambiguate from the trading
    pipeline's :class:`src.orchestration.squad_orchestrator.SquadOrchestrator`
    (R2). This is part of the non-trading "BuildToValue" agent cluster.
    """

    architect: ArchitectAgent = field(default_factory=ArchitectAgent)
    developer: DeveloperAgent = field(default_factory=DeveloperAgent)

    async def delegate_task(self, task: str) -> Dict[str, Any]:
        plan = self.architect.reason_with_cot(task)
        developer_result = await self.developer.react_loop(task)
        return {"plan": plan, "implementation": developer_result}
