"""Unit tests for the HITL order store (lifecycle, auto-approval, bridge)."""
from __future__ import annotations

import asyncio

import pytest

from src.core.ledger import TradingLedger
from src.hitl.orders import (
    Order,
    OrderConflictError,
    OrderStatus,
    OrderStore,
    make_approval_handler,
)
from src.safety.guardrails import GuardrailSystem


@pytest.fixture
def ledger(tmp_path) -> TradingLedger:
    return TradingLedger(tmp_path / "trades.jsonl")


def _order(notional_price=100.0, qty=1.0, critical=False) -> Order:
    return Order(
        pair="BTC/USDT",
        side="buy",
        quantity=qty,
        price=notional_price,
        strategy="dca",
        agent_id="strategy_agent",
        confidence=0.8,
        reason="RSI oversold, DCA schedule reached",
        critical=critical,
        position_size_pct=2.0,
        stop_loss=notional_price * 0.97,
        take_profit=notional_price * 1.08,  # RR 2.67 -> passes guardrails
    )


def test_submit_below_threshold_auto_fills(ledger):
    store = OrderStore(ledger, threshold_provider=lambda: 1_000.0)
    order = store.submit(_order(notional_price=100.0, qty=1.0))  # notional 100
    assert order.status == OrderStatus.filled
    assert order.auto_approved is True
    # A fill was logged to the ledger.
    assert len(ledger.get_events("order_fill")) == 1


def test_submit_above_threshold_stays_pending(ledger):
    store = OrderStore(ledger, threshold_provider=lambda: 1_000.0)
    order = store.submit(_order(notional_price=100.0, qty=50.0))  # notional 5000
    assert order.status == OrderStatus.pending
    assert order.auto_approved is False
    assert store.pending_count() == 1


def test_level_zero_threshold_forces_pending(ledger):
    store = OrderStore(ledger, threshold_provider=lambda: 0.0)
    order = store.submit(_order(notional_price=1.0, qty=1.0))
    assert order.status == OrderStatus.pending


def test_critical_order_pending_even_below_threshold(ledger):
    store = OrderStore(ledger, threshold_provider=lambda: 5_000.0)
    order = store.submit(_order(notional_price=100.0, qty=1.0, critical=True))
    assert order.status == OrderStatus.pending


def test_resolve_approve_fills(ledger):
    store = OrderStore(ledger, threshold_provider=lambda: 0.0)
    order = store.submit(_order())
    resolved = store.resolve(order.id, approved=True, operator="daniel")
    assert resolved.status == OrderStatus.filled
    assert resolved.operator_id == "daniel"
    assert len(ledger.get_events("order_fill")) == 1


def test_resolve_reject_sets_rejected(ledger):
    store = OrderStore(ledger, threshold_provider=lambda: 0.0)
    order = store.submit(_order())
    resolved = store.resolve(order.id, approved=False, operator="roberto", operator_note="risco alto")
    assert resolved.status == OrderStatus.rejected
    assert resolved.operator_note == "risco alto"
    assert len(ledger.get_events("order_fill")) == 0


def test_resolve_non_pending_raises_conflict(ledger):
    store = OrderStore(ledger, threshold_provider=lambda: 0.0)
    order = store.submit(_order())
    store.resolve(order.id, approved=True)
    with pytest.raises(OrderConflictError):
        store.resolve(order.id, approved=False, operator_note="late")


def test_resolve_unknown_raises_keyerror(ledger):
    store = OrderStore(ledger, threshold_provider=lambda: 0.0)
    with pytest.raises(KeyError):
        store.resolve("ord_missing", approved=True)


def test_list_filters_by_status(ledger):
    store = OrderStore(ledger, threshold_provider=lambda: 0.0)
    a = store.submit(_order())
    store.submit(_order())
    store.resolve(a.id, approved=True)
    assert len(store.list(status=OrderStatus.pending)) == 1
    assert len(store.list(status=OrderStatus.filled)) == 1


@pytest.mark.asyncio
async def test_bridge_handler_blocks_until_resolved(ledger):
    store = OrderStore(ledger, threshold_provider=lambda: 0.0)  # always pending
    handler = make_approval_handler(store)
    signal = {"symbol": "BTC/USDT", "action": "buy", "entry_price": 100.0,
              "quantity": 1.0, "confidence": 0.8, "reason": "x" * 12}

    task = asyncio.create_task(handler(signal))
    await asyncio.sleep(0.01)  # let the handler register the pending order
    pending = store.list(status=OrderStatus.pending)
    assert len(pending) == 1

    store.resolve(pending[0].id, approved=True, operator="daniel")
    approved = await asyncio.wait_for(task, timeout=1.0)
    assert approved is True


@pytest.mark.asyncio
async def test_bridge_handler_auto_approves(ledger):
    store = OrderStore(ledger, threshold_provider=lambda: 10_000.0)  # auto
    handler = make_approval_handler(store)
    signal = {"symbol": "BTC/USDT", "action": "buy", "entry_price": 100.0,
              "quantity": 1.0, "confidence": 0.8, "reason": "x" * 12}
    approved = await asyncio.wait_for(handler(signal), timeout=1.0)
    assert approved is True


@pytest.mark.asyncio
async def test_wait_for_decision_timeout_auto_cancels(ledger):
    # No human responds within the (tiny) window -> auto-cancel, fail-closed.
    store = OrderStore(ledger, threshold_provider=lambda: 0.0, decision_timeout=0.05)
    order = store.submit(_order())
    approved = await store.wait_for_decision(order.id)
    assert approved is False
    assert store.get(order.id).status == OrderStatus.cancelled


def test_transitions_emit_process_events(ledger):
    store = OrderStore(ledger, threshold_provider=lambda: 0.0)
    order = store.submit(_order())
    store.resolve(order.id, approved=True, operator="daniel")
    activities = [e["data"]["activity"] for e in ledger.get_process_events(order.id)]
    assert "order_submitted" in activities
    assert "order_filled" in activities


def test_reject_emits_rejected_event(ledger):
    store = OrderStore(ledger, threshold_provider=lambda: 0.0)
    order = store.submit(_order())
    store.resolve(order.id, approved=False, operator_note="risco")
    activities = [e["data"]["activity"] for e in ledger.get_process_events(order.id)]
    assert "order_rejected" in activities


# ----------------------------------------------------------------- guardrail gate
def test_guardrails_reject_before_threshold(ledger):
    # Even with a huge auto-approve threshold, a risk violation rejects first.
    store = OrderStore(
        ledger, threshold_provider=lambda: 1_000_000.0, guardrails=GuardrailSystem()
    )
    bad = _order()
    bad.take_profit = bad.price * 1.01  # RR ~0.33 -> violates
    out = store.submit(bad)
    assert out.status == OrderStatus.rejected
    assert "Risk-reward" in out.operator_note
    activities = [e["data"]["activity"] for e in ledger.get_process_events(out.id)]
    assert "order_rejected" in activities


def test_guardrails_pass_then_auto_fill(ledger):
    store = OrderStore(
        ledger, threshold_provider=lambda: 1_000_000.0, guardrails=GuardrailSystem()
    )
    out = store.submit(_order())  # compliant
    assert out.status == OrderStatus.filled


def test_guardrails_failure_never_raises(ledger):
    class _Boom(GuardrailSystem):
        def validate_order(self, order):
            raise RuntimeError("guardrail engine down")

    store = OrderStore(ledger, threshold_provider=lambda: 100.0, guardrails=_Boom())
    out = store.submit(_order())  # must not raise; defensive reject
    assert out.status == OrderStatus.rejected
    assert "risk validation error" in out.operator_note
