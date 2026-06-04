"""Unit tests for the SQLite-backed HITL order store (Phase 5a-ii)."""
from __future__ import annotations

import asyncio
import uuid

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


def _store(ledger, *, db_path=None, **kw) -> OrderStore:
    """OrderStore on a unique temp DB (fast polling), unless db_path is shared."""
    if db_path is None:
        db_path = ledger.ledger_path.parent / f"orders_{uuid.uuid4().hex}.db"
    kw.setdefault("poll_interval", 0.02)
    return OrderStore(ledger, db_path=str(db_path), **kw)


def _order(price=100.0, qty=1.0, critical=False) -> Order:
    return Order(
        pair="BTC/USDT", side="buy", quantity=qty, price=price,
        strategy="dca", agent_id="strategy_agent", confidence=0.8,
        reason="RSI oversold, DCA schedule reached", critical=critical,
        position_size_pct=2.0, stop_loss=price * 0.97, take_profit=price * 1.08,
    )


# ----------------------------------------------------------------- submit / auto
def test_submit_below_threshold_auto_fills(ledger):
    store = _store(ledger, threshold_provider=lambda: 1_000.0)
    order = store.submit(_order(price=100.0, qty=1.0))  # notional 100
    assert order.status == OrderStatus.filled
    assert order.auto_approved is True
    assert len(ledger.get_events("order_fill")) == 1


def test_submit_above_threshold_stays_pending(ledger):
    store = _store(ledger, threshold_provider=lambda: 1_000.0)
    order = store.submit(_order(price=100.0, qty=50.0))  # notional 5000
    assert order.status == OrderStatus.pending
    assert store.pending_count() == 1


def test_level_zero_threshold_forces_pending(ledger):
    store = _store(ledger, threshold_provider=lambda: 0.0)
    assert store.submit(_order()).status == OrderStatus.pending


def test_critical_order_pending_even_below_threshold(ledger):
    store = _store(ledger, threshold_provider=lambda: 5_000.0)
    assert store.submit(_order(critical=True)).status == OrderStatus.pending


# ----------------------------------------------------------------- resolve
def test_resolve_approve_sets_approved_not_filled(ledger):
    # Model B: manual approval -> 'approved'; the loop fills via mark_filled.
    store = _store(ledger, threshold_provider=lambda: 0.0)
    order = store.submit(_order())
    resolved = store.resolve(order.id, approved=True, operator="daniel")
    assert resolved.status == OrderStatus.approved
    assert resolved.operator_id == "daniel"
    assert len(ledger.get_events("order_fill")) == 0  # not filled yet


def test_resolve_reject_sets_rejected(ledger):
    store = _store(ledger, threshold_provider=lambda: 0.0)
    order = store.submit(_order())
    resolved = store.resolve(order.id, approved=False, operator="roberto", operator_note="risco alto")
    assert resolved.status == OrderStatus.rejected
    assert resolved.operator_note == "risco alto"
    assert len(ledger.get_events("order_fill")) == 0


def test_resolve_non_pending_raises_conflict(ledger):
    store = _store(ledger, threshold_provider=lambda: 0.0)
    order = store.submit(_order())
    store.resolve(order.id, approved=True)  # -> approved (no longer pending)
    with pytest.raises(OrderConflictError):
        store.resolve(order.id, approved=False, operator_note="late")


def test_resolve_unknown_raises_keyerror(ledger):
    store = _store(ledger, threshold_provider=lambda: 0.0)
    with pytest.raises(KeyError):
        store.resolve("ord_missing", approved=True)


# ----------------------------------------------------------------- mark_filled
def test_mark_filled_transitions_approved_to_filled(ledger):
    store = _store(ledger, threshold_provider=lambda: 0.0)
    order = store.submit(_order())
    store.resolve(order.id, approved=True)
    filled = store.mark_filled(order.id, operator="loop")
    assert filled.status == OrderStatus.filled
    assert filled.filled_at is not None
    assert len(ledger.get_events("order_fill")) == 1


def test_mark_filled_noop_when_not_approved(ledger):
    # The WHERE status='approved' guard prevents filling a pending order.
    store = _store(ledger, threshold_provider=lambda: 0.0)
    order = store.submit(_order())  # pending
    result = store.mark_filled(order.id)
    assert result.status == OrderStatus.pending  # unchanged
    assert len(ledger.get_events("order_fill")) == 0


# ----------------------------------------------------------------- queries / lifecycle
def test_list_filters_by_status(ledger):
    store = _store(ledger, threshold_provider=lambda: 0.0)
    a = store.submit(_order())
    store.submit(_order())
    store.resolve(a.id, approved=True)  # a -> approved
    assert len(store.list(status=OrderStatus.pending)) == 1
    assert len(store.list(status=OrderStatus.approved)) == 1


def test_transitions_emit_process_events(ledger):
    store = _store(ledger, threshold_provider=lambda: 0.0)
    order = store.submit(_order())
    store.resolve(order.id, approved=True)
    store.mark_filled(order.id)
    activities = [e["data"]["activity"] for e in ledger.get_process_events(order.id)]
    assert "order_submitted" in activities
    assert "order_approved" in activities
    assert "order_filled" in activities


def test_reject_emits_rejected_event(ledger):
    store = _store(ledger, threshold_provider=lambda: 0.0)
    order = store.submit(_order())
    store.resolve(order.id, approved=False, operator_note="risco")
    activities = [e["data"]["activity"] for e in ledger.get_process_events(order.id)]
    assert "order_rejected" in activities


# ----------------------------------------------------------------- guardrail gate
def test_guardrails_reject_before_threshold(ledger):
    store = _store(ledger, threshold_provider=lambda: 1_000_000.0, guardrails=GuardrailSystem())
    bad = _order()
    bad.take_profit = bad.price * 1.01  # RR ~0.33 -> violates
    out = store.submit(bad)
    assert out.status == OrderStatus.rejected
    assert "Risk-reward" in out.operator_note


def test_guardrails_pass_then_auto_fill(ledger):
    store = _store(ledger, threshold_provider=lambda: 1_000_000.0, guardrails=GuardrailSystem())
    assert store.submit(_order()).status == OrderStatus.filled


def test_guardrails_failure_never_raises(ledger):
    class _Boom(GuardrailSystem):
        def validate_order(self, order):
            raise RuntimeError("guardrail engine down")

    store = _store(ledger, threshold_provider=lambda: 100.0, guardrails=_Boom())
    out = store.submit(_order())
    assert out.status == OrderStatus.rejected
    assert "risk validation error" in out.operator_note


# ----------------------------------------------------------------- bridge / cross-process
@pytest.mark.asyncio
async def test_bridge_handler_blocks_until_resolved(ledger):
    store = _store(ledger, threshold_provider=lambda: 0.0)  # always pending
    handler = make_approval_handler(store)
    signal = {"symbol": "BTC/USDT", "action": "buy", "entry_price": 100.0,
              "quantity": 1.0, "confidence": 0.8, "reason": "x" * 12}

    task = asyncio.create_task(handler(signal))
    await asyncio.sleep(0.05)
    pending = store.list(status=OrderStatus.pending)
    assert len(pending) == 1

    store.resolve(pending[0].id, approved=True, operator="daniel")
    assert await asyncio.wait_for(task, timeout=2.0) is True


@pytest.mark.asyncio
async def test_bridge_handler_auto_approves(ledger):
    store = _store(ledger, threshold_provider=lambda: 10_000.0)  # auto
    handler = make_approval_handler(store)
    signal = {"symbol": "BTC/USDT", "action": "buy", "entry_price": 100.0,
              "quantity": 1.0, "confidence": 0.8, "reason": "x" * 12}
    assert await asyncio.wait_for(handler(signal), timeout=1.0) is True


@pytest.mark.asyncio
async def test_cross_process_decision_via_shared_db(tmp_path):
    # Two OrderStore instances (simulating loop + API) on the SAME db file.
    db = tmp_path / "shared.db"
    loop_ledger = TradingLedger(tmp_path / "loop.jsonl")
    api_ledger = TradingLedger(tmp_path / "api.jsonl")
    loop_store = OrderStore(loop_ledger, threshold_provider=lambda: 0.0,
                            db_path=str(db), poll_interval=0.2)
    api_store = OrderStore(api_ledger, threshold_provider=lambda: 0.0, db_path=str(db))

    order = loop_store.submit(_order())  # loop submits -> pending in shared DB
    waiter = asyncio.create_task(loop_store.wait_for_decision(order.id, timeout=5))
    await asyncio.sleep(0.1)

    # The "API" process resolves on the same DB.
    api_store.resolve(order.id, approved=True, operator="daniel")

    # Loop detects within ~2 polls (<= 4s).
    assert await asyncio.wait_for(waiter, timeout=4.0) is True
    assert api_store.get(order.id).status == OrderStatus.approved


@pytest.mark.asyncio
async def test_wait_for_decision_timeout_auto_cancels(ledger):
    store = _store(ledger, threshold_provider=lambda: 0.0, decision_timeout=0.05)
    order = store.submit(_order())
    assert await store.wait_for_decision(order.id) is False
    assert store.get(order.id).status == OrderStatus.cancelled
