"""Shared pytest fixtures for the CriptoTrade test suite.

Centralizes the test doubles that were previously duplicated across
``test_agents.py`` and ``test_trading_flow.py`` (see audit report:
"Sem fixtures compartilhados").
"""
from __future__ import annotations

from typing import Any, Dict

import pytest


class DummyExchange:
    """Minimal exchange stub — no network, safe for unit/integration tests."""


@pytest.fixture
def dummy_exchange() -> DummyExchange:
    """Return a fresh exchange stub instance."""
    return DummyExchange()


@pytest.fixture
def squad_approval():
    """HITL handler for ``SquadOrchestrator`` (signature: ``(order) -> bool``)."""

    async def _approve(_order: Dict[str, Any]) -> bool:
        return True

    return _approve


@pytest.fixture
def autonomy_approval():
    """HITL handler for ``ProgressiveAutonomyManager`` (``(agent, action) -> dict``)."""

    async def _approve(_agent: str, _action: Dict[str, Any]) -> Dict[str, Any]:
        return {"approved": True, "modifications": None, "feedback": None}

    return _approve
