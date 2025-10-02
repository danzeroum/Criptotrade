"""Agente supervisor responsável por orquestrar fluxos multiagente."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class Agent(Protocol):
    """Protocolo mínimo para agentes especializados."""

    name: str

    async def arun(self, task: str) -> str:  # pragma: no cover - interface
        """Executa uma tarefa assíncrona e retorna o resultado."""


@dataclass
class SupervisorAgent:
    """Coordenador de agentes especialistas."""

    orchestrator: Agent
    specialists: list[Agent] = field(default_factory=list)

    async def run(self, task: str) -> str:
        """Delegar uma tarefa e combinar os resultados."""

        summary = await self.orchestrator.arun(task)
        outputs: list[str] = []
        for agent in self.specialists:
            outputs.append(await agent.arun(summary))
        return "\n".join(outputs)
