import asyncio

import pytest

from src.agents.execution_agent import ExecutionAgent
from src.agents.risk_agent import RiskAgent
from src.agents.strategy_agent import StrategyAgent


@pytest.mark.asyncio
async def test_strategy_agent_generates_signal():
    agent = StrategyAgent()
    result = await agent.execute({"symbol": "BTC/USDT", "timeframe": "1h"})
    assert result["success"] is True
    assert result["signal"]["action"] == "BUY"
    assert result["confidence"] >= 0.0


@pytest.mark.asyncio
async def test_risk_agent_validates_signal():
    agent = RiskAgent()
    signal = {
        "position_size_pct": 3.0,
        "entry_price": 100.0,
        "stop_loss": 97.0,
        "take_profit": 105.0,
    }
    result = await agent.execute({"signal": signal, "portfolio": {}})
    assert result["success"] is True
    assert result["approved"] is True


class _DummyExchange:
    pass


@pytest.mark.asyncio
async def test_execution_agent_requires_hitl():
    agent = ExecutionAgent(_DummyExchange())
    result = await agent.execute({"signal": {}, "human_approved": False})
    assert result["success"] is False
    assert result["error"] == "Human approval required (HITL)"


@pytest.mark.asyncio
async def test_execution_agent_simulates_order():
    agent = ExecutionAgent(_DummyExchange())
    result = await agent.execute({
        "signal": {"action": "BUY", "symbol": "BTC/USDT"},
        "human_approved": True,
    })
    assert result["success"] is True
    assert result["order_id"].startswith("PAPER_")
