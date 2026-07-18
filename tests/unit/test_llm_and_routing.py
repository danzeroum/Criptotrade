"""Tests for the optional LLM layer, ORDER_ROUTING, and env-driven risk limits."""
from __future__ import annotations

import pytest

from src.agents.risk_agent import RiskAgent
from src.agents.strategy_agent import StrategyAgent
from src.core import llm_client
from src.core.exchange_client import ExchangeClient
from src.safety.guardrails import GuardrailSystem


# --------------------------------------------------------------------- llm_client
def test_is_llm_enabled_default_false(monkeypatch):
    monkeypatch.delenv("LLM_ENABLED", raising=False)
    llm_client.reset_llm_client()
    assert llm_client.is_llm_enabled() is False
    assert llm_client.get_llm_client() is None


def test_is_llm_enabled_requires_flag_and_key(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER", "google")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    llm_client.reset_llm_client()
    assert llm_client.is_llm_enabled() is False  # flag on but no key

    monkeypatch.setenv("GOOGLE_API_KEY", "k-123")
    llm_client.reset_llm_client()
    assert llm_client.is_llm_enabled() is True


def test_deepseek_provider_gating_and_defaults(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    llm_client.reset_llm_client()
    assert llm_client.is_llm_enabled() is False  # flag on but no DeepSeek key

    monkeypatch.setenv("DEEPSEEK_API_KEY", "k-deepseek")
    llm_client.reset_llm_client()
    assert llm_client.is_llm_enabled() is True
    client = llm_client.get_llm_client()
    assert client is not None
    assert client.provider == "deepseek"
    assert client.model == "deepseek-chat"  # -chat, never -reasoner (latency)


def test_deepseek_builds_openai_client_against_deepseek_base(monkeypatch):
    pytest.importorskip("langchain_openai")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k-deepseek")
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    chat = llm_client.LLMClient(provider="deepseek")._build_chat()
    assert chat.model_name == "deepseek-chat"
    assert chat.openai_api_base == "https://api.deepseek.com"

    # The base URL stays overridable (proxies / compatible gateways).
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://proxy.example/v1")
    chat = llm_client.LLMClient(provider="deepseek")._build_chat()
    assert chat.openai_api_base == "https://proxy.example/v1"


def test_extract_json_handles_fenced_and_bare():
    assert llm_client._extract_json('{"a": 1}') == {"a": 1}
    fenced = "```json\n{\"confidence\": 0.8, \"thesis\": \"x\"}\n```"
    assert llm_client._extract_json(fenced) == {"confidence": 0.8, "thesis": "x"}
    assert llm_client._extract_json("no json here") is None


# ----------------------------------------------------------------- StrategyAgent
class _FakeLLM:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    async def reason_json(self, system, user):
        self.calls += 1
        return self.payload


@pytest.mark.asyncio
async def test_strategy_without_llm_is_deterministic():
    agent = StrategyAgent(exchange_client=None, llm_client=None)
    result = await agent.execute({"symbol": "BTC/USDT"})
    assert result["llm_used"] is False
    assert result["llm_thesis"] is None
    assert result["stub_used"] is True  # no exchange client -> stub analysis


@pytest.mark.asyncio
async def test_strategy_blends_llm_confidence_and_thesis():
    fake = _FakeLLM({"confidence": 0.9, "thesis": "strong bullish breakout"})
    agent = StrategyAgent(exchange_client=None, llm_client=fake)
    result = await agent.execute({"symbol": "BTC/USDT"})
    assert fake.calls == 1
    assert result["llm_used"] is True
    assert result["llm_thesis"] == "strong bullish breakout"
    assert 0.10 <= result["confidence"] <= 0.95


@pytest.mark.asyncio
async def test_strategy_llm_failure_falls_back_to_deterministic():
    fake = _FakeLLM(None)  # LLM returned nothing
    agent = StrategyAgent(exchange_client=None, llm_client=fake)
    result = await agent.execute({"symbol": "BTC/USDT"})
    assert result["llm_used"] is False  # blend skipped


# ------------------------------------------------------------------- RiskAgent LLM
@pytest.mark.asyncio
async def test_risk_llm_reflection_can_only_tighten():
    fake = _FakeLLM({"hidden_risk": True, "note": "thin liquidity at this level"})
    agent = RiskAgent(llm_client=fake)
    signal = {
        "action": "BUY", "entry_price": 100.0, "stop_loss": 95.0,
        "take_profit": 115.0, "position_size_pct": 2.0,
    }
    out = await agent.execute({"signal": signal, "portfolio": {}})
    # Approval is rule-based; reflection only adds caution / review flag.
    assert "validation" in out
    assert out["validation"].get("requires_review") is True


# ---------------------------------------------------------------- ORDER_ROUTING
def test_order_routing_defaults_to_paper(monkeypatch):
    monkeypatch.setenv("EXCHANGE_DRY_RUN", "true")
    monkeypatch.delenv("ORDER_ROUTING", raising=False)
    client = ExchangeClient()
    assert client.paper_trading is True


def test_order_routing_live_requires_real_data(monkeypatch):
    monkeypatch.setenv("EXCHANGE_DRY_RUN", "true")
    monkeypatch.setenv("ORDER_ROUTING", "live")
    with pytest.raises(RuntimeError, match="ORDER_ROUTING=live"):
        ExchangeClient()


def test_order_routing_invalid_value_raises(monkeypatch):
    monkeypatch.setenv("EXCHANGE_DRY_RUN", "true")
    monkeypatch.setenv("ORDER_ROUTING", "bogus")
    with pytest.raises(RuntimeError, match="ORDER_ROUTING"):
        ExchangeClient()


def test_order_routing_live_with_real_data_enables_live(monkeypatch):
    # Real market data + live routing: constructs a (offline) ccxt client and
    # flips paper_trading off. No network call happens at construction time.
    monkeypatch.setenv("EXCHANGE_DRY_RUN", "false")
    monkeypatch.setenv("ORDER_ROUTING", "live")
    client = ExchangeClient()
    assert client.paper_trading is False


# ------------------------------------------------------- MAX_POSITION_SIZE_PCT env
def test_guardrail_position_size_respects_env(monkeypatch):
    monkeypatch.setenv("MAX_POSITION_SIZE_PCT", "2.0")
    gs = GuardrailSystem()
    ok, msg = gs.check_position_size({"position_size_pct": 3.0})
    assert ok is False and "2.0" in msg

    monkeypatch.setenv("MAX_POSITION_SIZE_PCT", "5.0")
    ok, _ = gs.check_position_size({"position_size_pct": 3.0})
    assert ok is True


def test_risk_agent_reads_position_size_env(monkeypatch):
    monkeypatch.setenv("MAX_POSITION_SIZE_PCT", "1.5")
    agent = RiskAgent(llm_client=None)
    assert agent.max_position_size_pct == 1.5
