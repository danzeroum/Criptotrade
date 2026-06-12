"""Fase 5b: wait_for_decision must fail fast for an unknown order id."""
from __future__ import annotations

import time

import pytest

from src.core.alerts import AlertStore, make_guardrail_sink
from src.core.ledger import TradingLedger
from src.hitl.orders import OrderStore
from src.safety.guardrails import GuardrailSystem


def _store(tmp_path) -> OrderStore:
    ledger = TradingLedger(tmp_path / "trades.jsonl")
    return OrderStore(
        ledger,
        threshold_provider=lambda: 1000.0,
        guardrails=GuardrailSystem(alert_sink=make_guardrail_sink(AlertStore(tmp_path / "a.jsonl"))),
        db_path=str(tmp_path / "orders.db"),
    )


@pytest.mark.asyncio
async def test_wait_for_decision_returns_false_fast_for_unknown_id(tmp_path):
    store = _store(tmp_path)
    start = time.monotonic()
    result = await store.wait_for_decision("does-not-exist", timeout=5.0)
    elapsed = time.monotonic() - start
    assert result is False
    # The whole point of the fix: don't block for the full 5s timeout.
    assert elapsed < 1.0, f"waited {elapsed:.2f}s for a non-existent order"
