"""Abstrações para ferramentas utilizadas por agentes."""
from __future__ import annotations

from typing import Awaitable, Callable

AsyncTool = Callable[[str], Awaitable[str]]


def wrap_sync_tool(tool: Callable[[str], str]) -> AsyncTool:
    """Converte uma função síncrona em ferramenta assíncrona."""

    async def _async_tool(input_text: str) -> str:
        return tool(input_text)

    return _async_tool
