"""Ponto de entrada demonstrativo para a metodologia BuildToValue v6.1."""
from __future__ import annotations

import asyncio

from src.agents.supervisor_agent import SupervisorAgent
from src.utils.memory_utils import MemoryStore


async def main() -> None:
    """Executa um fluxo simples de demonstração."""

    memory = MemoryStore()
    memory.set("usuario", "João")

    async def dummy_agent(task: str) -> str:
        return f"{memory.get('usuario')}: {task}"

    supervisor = SupervisorAgent(
        orchestrator=type("Orchestrator", (), {"name": "orchestrator", "arun": staticmethod(dummy_agent)})(),
        specialists=[type("Writer", (), {"name": "writer", "arun": staticmethod(dummy_agent)})()],
    )

    resultado = await supervisor.run("Preparar relatório executivo")
    print(resultado)


if __name__ == "__main__":
    asyncio.run(main())
