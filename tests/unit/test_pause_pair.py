"""N9 — pause per pair: a paused pair opens NO new order, but its open positions
stay managed (stop/TP still fire). The gate lives inside ``analyze_and_trade``,
after the position check and before the new-order pipeline.

Aceite (doc N9): "Pausar um par interrompe novas ordens dele no ciclo seguinte sem
restart; posições abertas seguem geridas (stop/TP)."
"""
from __future__ import annotations

import pytest

from src.core.ledger import TradingLedger
from src.orchestration.squad_orchestrator import SquadOrchestrator


class _DummyExchange:
    async def create_order(self, symbol, order_type, side, amount, price=None, params=None):
        import uuid

        return {"id": "PAPER_" + uuid.uuid4().hex[:8], "status": "filled"}


class _StubStrategy:
    """Returns a fixed, high-confidence signal — ``entry_price`` becomes the
    ``current_price`` that ``_check_open_positions`` evaluates stop/TP against."""

    def __init__(self, entry_price: float, action: str = "buy", confidence: float = 0.9):
        self._signal = {"action": action, "entry_price": entry_price, "position_size_pct": 5.0}
        self._confidence = confidence
        self.calls = 0

    async def execute(self, ctx):
        self.calls += 1
        return {"signal": dict(self._signal), "confidence": self._confidence}


async def _approve(order):
    return True


def _make_orch(tmp_path, entry_price):
    ledger = TradingLedger(tmp_path / "trades.jsonl")
    orch = SquadOrchestrator(_DummyExchange(), approval_handler=_approve)
    orch.ledger = ledger
    orch.strategy_agent = _StubStrategy(entry_price)  # deterministic price/signal
    return orch, ledger


@pytest.mark.asyncio
async def test_paused_pair_still_closes_on_stop(tmp_path):
    # Open a long at 100 with a stop at 95; the next cycle prices it at 90 (stop hit).
    orch, ledger = _make_orch(tmp_path, entry_price=90.0)
    orch._match_or_open(symbol="BTC/USDT", side="buy", price=100.0,
                        quantity=1.0, fee=0.0, order_id="b1", stop_loss=95.0)

    result = await orch.analyze_and_trade("BTC/USDT", paused=True)

    # New orders are cut...
    assert result == {"success": False, "reason": "paused"}
    assert "order_id" not in result
    # ...but the open position was still managed: the stop fired and closed it.
    closed = ledger.get_events("position_closed")
    assert len(closed) == 1
    assert closed[0]["data"]["exit_price"] == 95.0
    assert orch._open_positions == {}
    # And the skip is visible in the feed as reason "paused".
    skips = ledger.get_events("signal_skipped")
    assert [s["data"]["reason"] for s in skips] == ["paused"]
    # No new order/signal was logged for the paused pair.
    assert ledger.get_events("signal_generated") == []


@pytest.mark.asyncio
async def test_paused_pair_without_position_opens_nothing(tmp_path):
    orch, ledger = _make_orch(tmp_path, entry_price=100.0)
    result = await orch.analyze_and_trade("ETH/USDT", paused=True)
    assert result == {"success": False, "reason": "paused"}
    assert orch._open_positions == {}
    assert ledger.get_events("position_closed") == []


@pytest.mark.asyncio
async def test_paused_skip_is_transition_only_no_heartbeat(tmp_path):
    # Pause is a persistent config state — it must emit ONE signal_skipped on the
    # transition, never a per-cycle heartbeat (unlike no_slot/circuit_breaker).
    orch, ledger = _make_orch(tmp_path, entry_price=100.0)
    for _ in range(5):
        await orch.analyze_and_trade("BTC/USDT", paused=True)
    skips = ledger.get_events("signal_skipped")
    assert len(skips) == 1, "paused must not heartbeat — one event across many cycles"
    assert skips[0]["data"]["reason"] == "paused"


@pytest.mark.asyncio
async def test_not_paused_pair_runs_the_pipeline(tmp_path):
    # Control: with paused=False the pair is not gated — the strategy signal is
    # logged and the pipeline proceeds past the pause point.
    orch, ledger = _make_orch(tmp_path, entry_price=100.0)
    await orch.analyze_and_trade("BTC/USDT", paused=False)
    assert ledger.get_events("signal_generated"), "an un-paused pair logs its signal"
    assert [s["data"]["reason"] for s in ledger.get_events("signal_skipped")] != ["paused"]
