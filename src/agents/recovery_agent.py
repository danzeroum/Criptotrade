"""Agente dedicado à recuperação após anomalias."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RecoveryAgent:
    """Executa procedimentos de mitigação e recuperação."""

    remediation_tool: callable

    async def arun(self, incident_report: str) -> str:
        """Aciona rotinas de recuperação baseadas no relatório recebido."""

        result = await self.remediation_tool(incident_report)
        return f"Recovery actions: {result}"
