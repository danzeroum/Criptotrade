import pytest

from src.orchestration.squad_orchestrator import SquadOrchestrator
from src.core.ledger import TradingLedger


class _DummyExchange:
    pass


async def _approve(order):
    return True


@pytest.mark.asyncio
async def test_analyze_and_trade_success(tmp_path):
    orchestrator = SquadOrchestrator(_DummyExchange(), approval_handler=_approve)
    ledger_path = tmp_path / "trades.jsonl"
    orchestrator.ledger = TradingLedger(ledger_path)

    result = await orchestrator.analyze_and_trade("BTC/USDT", timeframe="1h")

    assert result["success"] is True
    assert result["order_id"].startswith("PAPER_")
    assert ledger_path.exists()
    entries = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(entries) >= 3  # signal, validation, execution


@pytest.mark.asyncio
async def test_analyze_and_trade_blocked_when_no_hitl_handler(tmp_path):
    # Fail-closed: with no approval handler, the trade must be rejected.
    orchestrator = SquadOrchestrator(_DummyExchange())
    orchestrator.ledger = TradingLedger(tmp_path / "trades.jsonl")

    result = await orchestrator.analyze_and_trade("BTC/USDT", timeframe="1h")

    assert result["success"] is False
    assert result["reason"] == "Human rejected the trade"


@pytest.mark.asyncio
async def test_analyze_and_trade_rejected_when_low_confidence(tmp_path, monkeypatch):
    orchestrator = SquadOrchestrator(_DummyExchange())
    orchestrator.ledger = TradingLedger(tmp_path / "trades.jsonl")

    async def low_confidence_execute(task):
        return {
            "success": True,
            "agent": "strategy",
            "signal": {"action": "BUY", "symbol": task["symbol"]},
            "confidence": 0.2,
            "analysis": {},
        }

    monkeypatch.setattr(orchestrator.strategy_agent, "execute", low_confidence_execute)

    result = await orchestrator.analyze_and_trade("ETH/USDT")

    assert result["success"] is False
    assert result["reason"] == "Low confidence signal"
