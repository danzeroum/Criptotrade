"""Shared pytest fixtures for the CriptoTrade test suite.

Centralizes the test doubles that were previously duplicated across
``test_agents.py`` and ``test_trading_flow.py`` (see audit report:
"Sem fixtures compartilhados").
"""
from __future__ import annotations

from typing import Any

import pytest


class DummyExchange:
    """Minimal exchange stub — no network, safe for unit/integration tests."""

    async def create_order(self, symbol, order_type, side, amount, price=None, params=None):
        """Bare paper fill (no slippage/fee) so existing P&L assertions hold.

        The real slippage/fee path lives in ``ExchangeClient._create_paper_order``
        and is exercised separately; this double only needs a valid PAPER_ id.
        """
        import uuid

        return {
            "id": "PAPER_" + uuid.uuid4().hex[:8],
            "symbol": symbol,
            "type": order_type,
            "side": side,
            "amount": amount,
            "status": "filled",
        }


@pytest.fixture
def dummy_exchange() -> DummyExchange:
    """Return a fresh exchange stub instance."""
    return DummyExchange()


@pytest.fixture
def squad_approval():
    """HITL handler for ``SquadOrchestrator`` (signature: ``(order) -> bool``)."""

    async def _approve(_order: dict[str, Any]) -> bool:
        return True

    return _approve


@pytest.fixture
def autonomy_approval():
    """HITL handler for ``ProgressiveAutonomyManager`` (``(agent, action) -> dict``)."""

    async def _approve(_agent: str, _action: dict[str, Any]) -> dict[str, Any]:
        return {"approved": True, "modifications": None, "feedback": None}

    return _approve
