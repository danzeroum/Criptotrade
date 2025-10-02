"""Agente dedicado à exploração de ambientes de rede."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExplorationAgent:
    """Responsável por varrer um ambiente em busca de vulnerabilidades."""

    scanner_tool: callable

    async def arun(self, instruction: str) -> str:
        """Executa um scan e retorna um relatório textual."""

        result = await self.scanner_tool(instruction)
        return f"Exploration report: {result}"
