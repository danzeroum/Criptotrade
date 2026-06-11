import asyncio

import pytest

from src.core.ledger import TradingLedger
from src.hitl.orders import OrderStatus, OrderStore, make_approval_handler
from src.orchestration.squad_orchestrator import SquadOrchestrator


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
async def test_manual_approval_completes_to_filled(tmp_path):
    # Follow-up #1: the manual path (approved -> loop executes -> filled).
    ledger = TradingLedger(tmp_path / "trades.jsonl")
    store = OrderStore(
        ledger, threshold_provider=lambda: 0.0,  # nothing auto-approves
        db_path=str(tmp_path / "orders.db"), poll_interval=0.02,
    )
    orchestrator = SquadOrchestrator(
        _DummyExchange(),
        approval_handler=make_approval_handler(store),
        fill_callback=store.mark_filled,
    )
    orchestrator.ledger = ledger

    task = asyncio.create_task(orchestrator.analyze_and_trade("BTC/USDT"))
    await asyncio.sleep(0.05)
    pending = store.list(status=OrderStatus.pending)
    assert len(pending) == 1
    assert pending[0].pair == "BTC/USDT"  # follow-up #2: symbol injected, not UNKNOWN

    # The "API" approves on the shared store; the loop executes and marks filled.
    store.resolve(pending[0].id, approved=True, operator="daniel")
    result = await asyncio.wait_for(task, timeout=2.0)
    assert result["success"] is True
    assert store.get(pending[0].id).status == OrderStatus.filled


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
