"""Extra coverage for hitl/orders.py — cancel, list/count with pair filter, make_approval_handler."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.hitl.orders import Order, OrderStatus, OrderStore, make_approval_handler
from src.core.ledger import TradingLedger


@pytest.fixture
def store(tmp_path) -> OrderStore:
    ledger = TradingLedger(tmp_path / "l.jsonl")
    return OrderStore(
        ledger=ledger,
        threshold_provider=lambda: 1_000_000.0,  # very high → all auto-approved
        db_path=str(tmp_path / "orders.db"),
    )


def _new_order(**kw) -> Order:
    base = dict(
        pair="BTC/USDT", side="buy", quantity=0.1, price=50_000.0,
        strategy="dca", agent_id="agent1", confidence=0.8,
        reason="test", critical=False, position_size_pct=2.0,
        stop_loss=None, take_profit=None,
    )
    base.update(kw)
    return Order(**base)


# ── cancel edge cases ────────────────────────────────────────────────────────

def test_cancel_nonexistent_order_returns_none(store):
    """Line 237: order is None → cancel returns None immediately."""
    result = store.cancel("does-not-exist")
    assert result is None


def test_cancel_already_filled_order_returns_order(store):
    """Line 237: order is not pending → cancel returns order unchanged."""
    order = _new_order()
    store.submit(order)
    # With threshold=1M, the order is auto-filled after submit
    filled = store.get(order.id)
    assert filled.status == OrderStatus.filled
    # Cancel the filled order → already not pending, returns it unchanged
    result = store.cancel(order.id)
    assert result is not None
    assert result.status == OrderStatus.filled


# ── list with pair filter ─────────────────────────────────────────────────────

def test_list_with_pair_filter_returns_only_matching(store):
    """Lines 265-266: list(pair=...) filters by pair."""
    order_btc = _new_order(pair="BTC/USDT")
    order_eth = _new_order(pair="ETH/USDT")
    store.submit(order_btc)
    store.submit(order_eth)

    btc_orders = store.list(pair="BTC/USDT")
    assert all(o.pair == "BTC/USDT" for o in btc_orders)
    assert len(btc_orders) >= 1

    eth_orders = store.list(pair="ETH/USDT")
    assert all(o.pair == "ETH/USDT" for o in eth_orders)


# ── count with pair filter ────────────────────────────────────────────────────

def test_count_with_pair_filter(store):
    """Lines 293-294: count(pair=...) filters by pair."""
    store.submit(_new_order(pair="BTC/USDT"))
    store.submit(_new_order(pair="ETH/USDT"))
    store.submit(_new_order(pair="BTC/USDT"))

    btc_count = store.count(pair="BTC/USDT")
    assert btc_count == 2

    eth_count = store.count(pair="ETH/USDT")
    assert eth_count == 1


# ── make_approval_handler ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_approval_handler_zero_price_returns_none(store):
    """Line 396: price=0 → handler returns None without inserting order."""
    handler = make_approval_handler(store)
    result = await handler({"entry_price": 0.0, "quantity": 0.1})
    assert result is None


@pytest.mark.asyncio
async def test_approval_handler_zero_quantity_and_no_position_size_returns_none(store):
    """Line 396: quantity=0 and can't derive from position_size → returns None."""
    handler = make_approval_handler(store)
    result = await handler({
        "entry_price": 50_000.0,
        "quantity": 0.0,
        "position_size_pct": 0.0,  # no fallback derivation possible
    })
    assert result is None


@pytest.mark.asyncio
async def test_approval_handler_rejected_order_returns_none(tmp_path):
    """Line 415: when guardrails reject the order, handler returns None."""
    from src.safety.guardrails import GuardrailSystem
    from src.core.ledger import TradingLedger

    ledger = TradingLedger(tmp_path / "l.jsonl")
    # GuardrailSystem that always rejects
    rejects_all = GuardrailSystem(rules=[lambda o: (False, "always rejected")])
    bad_store = OrderStore(
        ledger=ledger,
        threshold_provider=lambda: 1_000_000.0,
        guardrails=rejects_all,
        db_path=str(tmp_path / "orders.db"),
    )
    handler = make_approval_handler(bad_store)
    result = await handler({
        "entry_price": 50_000.0,
        "quantity": 0.1,
        "action": "buy",
        "symbol": "BTC/USDT",
    })
    assert result is None
