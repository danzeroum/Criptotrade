
import pytest

from src.agents.execution_agent import ExecutionAgent
from src.agents.ops_agent import OpsAgent
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


# ── OpsAgent ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ops_agent_returns_success():
    agent = OpsAgent()
    result = await agent.execute({"environment": "staging", "strategy": "blue-green"})
    assert result["success"] is True
    assert result["agent"] == "ops"
    assert result["confidence"] == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_ops_agent_defaults_unknown_strategy():
    agent = OpsAgent()
    result = await agent.execute({"environment": "production", "strategy": "unknown"})
    assert result["deployment"]["strategy"] == "blue-green"


@pytest.mark.asyncio
async def test_ops_agent_known_strategy_is_preserved():
    agent = OpsAgent()
    result = await agent.execute({"environment": "staging", "strategy": "canary"})
    assert result["deployment"]["strategy"] == "canary"


@pytest.mark.asyncio
async def test_ops_agent_monitoring_has_required_keys():
    agent = OpsAgent()
    result = await agent.execute({"environment": "staging"})
    mon = result["monitoring"]
    assert "metrics" in mon
    assert "alerts" in mon
    assert "dashboards" in mon
    assert "logging" in mon


@pytest.mark.asyncio
async def test_ops_agent_invalid_input_raises():
    agent = OpsAgent()
    with pytest.raises(ValueError, match="Invalid ops task payload"):
        await agent.execute(None)
