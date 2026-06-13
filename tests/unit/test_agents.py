
import pytest

from src.agents.execution_agent import ExecutionAgent
from src.agents.risk_agent import RiskAgent
from src.agents.strategy_agent import StrategyAgent
from src.core.exchange_client import ExchangeClient


@pytest.mark.asyncio
async def test_strategy_agent_generates_signal():
    # Without an exchange client the agent runs in stub mode and returns HOLD.
    # The important invariants are: succeeds, has a valid action, confidence is a float.
    agent = StrategyAgent()
    result = await agent.execute({"symbol": "BTC/USDT", "timeframe": "1h"})
    assert result["success"] is True
    assert result["signal"]["action"] in ("BUY", "SELL", "HOLD")
    assert isinstance(result["confidence"], float)
    assert 0.0 <= result["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_risk_agent_validates_signal():
    agent = RiskAgent()
    signal = {
        "position_size_pct": 3.0,
        "action": "BUY",
        "entry_price": 100.0,
        "stop_loss": 97.0,
        "take_profit": 108.0,  # RR 2.67 >= 2.5 so it clears the guardrails
    }
    result = await agent.execute({"signal": signal, "portfolio": {}})
    assert result["success"] is True
    assert result["approved"] is True


@pytest.mark.asyncio
async def test_risk_agent_rejects_guardrail_violation():
    # Same signal but RR 1.67 (< 2.5) -> guardrails now reject it.
    agent = RiskAgent()
    signal = {
        "position_size_pct": 3.0,
        "action": "BUY",
        "entry_price": 100.0,
        "stop_loss": 97.0,
        "take_profit": 105.0,
    }
    result = await agent.execute({"signal": signal, "portfolio": {}})
    assert result["approved"] is False
    assert any("Risk-reward" in i for i in result["validation"]["issues"])


class _DummyExchange:
    pass


@pytest.mark.asyncio
async def test_execution_agent_requires_hitl(dummy_exchange):
    agent = ExecutionAgent(dummy_exchange)
    result = await agent.execute({"signal": {}, "human_approved": False})
    assert result["success"] is False
    assert result["error"] == "Human approval required (HITL)"


@pytest.mark.asyncio
async def test_execution_agent_simulates_order(dummy_exchange):
    agent = ExecutionAgent(dummy_exchange)
    result = await agent.execute({
        "signal": {"action": "BUY", "symbol": "BTC/USDT"},
        "human_approved": True,
    })
    assert result["success"] is True
    assert result["order_id"].startswith("PAPER_")


@pytest.mark.asyncio
async def test_execution_agent_applies_slippage_and_fee(monkeypatch):
    # R1: an approved paper order must route through the exchange so the recorded
    # price reflects slippage and a non-zero fee — not the raw signal price.
    monkeypatch.setenv("EXCHANGE_DRY_RUN", "true")
    monkeypatch.setattr("time.time", lambda: 0.0)  # sin(0)=0 -> price == base
    agent = ExecutionAgent(ExchangeClient())
    result = await agent.execute({
        "signal": {"action": "BUY", "symbol": "BTC/USDT"},
        "human_approved": True,
        "quantity": 0.1,
    })
    assert result["success"] is True
    assert result["order_id"].startswith("PAPER_")
    # BTC base 50000 at ts=0; a buy slips +0.2% -> 50100.
    assert result["executed_price"] == pytest.approx(50000 * 1.002)
    assert result["fee"] == pytest.approx(0.1 * 50100 * 0.001)


@pytest.mark.asyncio
async def test_execution_agent_falls_back_without_quantity(dummy_exchange):
    # Defensive: an approved trade with no sizing must still record a paper fill
    # rather than crash (legacy synthetic id, no exchange call).
    agent = ExecutionAgent(dummy_exchange)
    result = await agent.execute({
        "signal": {"action": "BUY", "symbol": "BTC/USDT"},
        "human_approved": True,
    })
    assert result["success"] is True
    assert result["order_id"].startswith("PAPER_")
