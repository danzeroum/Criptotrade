"""Tests for position/circuit-breaker persistence (CT-002/CT-004) and the
pre-trade balance gate (CT-003)."""
from __future__ import annotations

import pytest

from src.agents.risk_agent import RiskAgent
from src.core.ledger import TradingLedger
from src.orchestration.position_store import (
    PositionStore,
    load_circuit_state,
    save_circuit_state,
)
from src.orchestration.squad_orchestrator import SquadOrchestrator

_POS = {
    "symbol": "BTC/USDT", "side": "buy", "entry_price": 100.0, "quantity": 0.5,
    "stop_loss": 95.0, "take_profit": 115.0, "opened_at": "2026-01-01T00:00:00+00:00",
}


# ------------------------------------------------------------- PositionStore (O1)
def test_position_store_roundtrip(tmp_path):
    db = tmp_path / "state.db"
    store = PositionStore(lambda: db)
    store.upsert("o1", _POS)
    loaded = store.load_all()
    assert "o1" in loaded
    assert loaded["o1"]["entry_price"] == 100.0
    assert loaded["o1"]["take_profit"] == 115.0

    store.delete("o1")
    assert store.load_all() == {}


def test_position_store_count(tmp_path):
    db = tmp_path / "state.db"
    store = PositionStore(lambda: db)
    assert store.count() == 0  # empty (table created on demand)

    store.upsert("o1", _POS)
    store.upsert("o2", _POS)
    assert store.count() == 2

    store.delete("o1")
    assert store.count() == 1


def test_circuit_state_roundtrip(tmp_path):
    db = tmp_path / "state.db"
    assert load_circuit_state(lambda: db) is None  # nothing persisted yet
    save_circuit_state(lambda: db, 123.0, 2, -3.5)
    state = load_circuit_state(lambda: db)
    assert state == {"tripped_at": 123.0, "consecutive_losses": 2, "daily_loss_pct": -3.5}


def test_orchestrator_restores_positions_after_restart(tmp_path):
    # First instance opens a position and mirrors it to the shared db.
    orch1 = SquadOrchestrator(object())
    orch1.ledger = TradingLedger(tmp_path / "trades.jsonl")
    orch1._open_positions["o1"] = dict(_POS)
    orch1._positions.upsert("o1", orch1._open_positions["o1"])

    # A fresh instance (simulating a loop restart) on the same db recovers it.
    orch2 = SquadOrchestrator(object())
    orch2.ledger = TradingLedger(tmp_path / "trades.jsonl")
    assert orch2._open_positions == {}  # nothing in memory yet
    orch2.reload_open_positions()
    assert "o1" in orch2._open_positions
    assert orch2._open_positions["o1"]["stop_loss"] == 95.0


def test_circuit_breaker_survives_restart(tmp_path):
    orch1 = SquadOrchestrator(object())
    orch1.ledger = TradingLedger(tmp_path / "trades.jsonl")
    # Three consecutive losses trips the breaker; state is persisted.
    for _ in range(3):
        orch1.circuit_breaker.record_trade_result(-1.0)
    assert orch1.circuit_breaker.is_open is True

    orch2 = SquadOrchestrator(object())
    orch2.ledger = TradingLedger(tmp_path / "trades.jsonl")
    orch2.reload_open_positions()  # also reloads breaker state
    assert orch2.circuit_breaker.is_open is True


# -------------------------------------------------------------- balance gate (O2)
@pytest.mark.asyncio
async def test_balance_gate_rejects_oversized_notional():
    agent = RiskAgent(llm_client=None)
    # size 5% is within the position-size limit, but notional (10000*5% = 500)
    # exceeds the available 100 -> rejected by the balance gate specifically.
    signal = {
        "action": "BUY", "entry_price": 100.0, "stop_loss": 95.0,
        "take_profit": 115.0, "position_size_pct": 5.0,
    }
    out = await agent.execute(
        {"signal": signal, "portfolio": {"available_capital": 100.0, "capital_base": 10000.0}}
    )
    assert out["approved"] is False
    assert any("Insufficient capital" in i for i in out["validation"]["issues"])


@pytest.mark.asyncio
async def test_balance_gate_allows_when_sufficient():
    agent = RiskAgent(llm_client=None)
    signal = {
        "action": "BUY", "entry_price": 100.0, "stop_loss": 95.0,
        "take_profit": 115.0, "position_size_pct": 2.0,
    }
    out = await agent.execute(
        {"signal": signal, "portfolio": {"available_capital": 10000.0, "capital_base": 10000.0}}
    )
    assert out["approved"] is True
