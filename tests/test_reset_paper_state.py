"""Operational reset of the paper breaker + open-position book.

Covers the store helpers (``PositionStore.clear`` / ``clear_circuit_state``) and
the ``reset_paper_state`` orchestration, including the ``--dry-run`` contract
(reports what *would* change, writes nothing).
"""
from __future__ import annotations

from src.core.ledger import TradingLedger
from src.orchestration.position_store import (
    PositionStore,
    clear_circuit_state,
    load_circuit_state,
    save_circuit_state,
)
from scripts.reset_paper_state import reset_paper_state

_POS = {
    "symbol": "BTC/USDT", "side": "buy", "entry_price": 100.0, "quantity": 0.5,
    "stop_loss": 95.0, "take_profit": 115.0, "opened_at": "2026-01-01T00:00:00+00:00",
}


def _provider(tmp_path):
    ledger = TradingLedger(tmp_path / "trades.jsonl")

    def db():
        return ledger.db_path

    return db


# ------------------------------------------------------------------ store helpers
def test_position_store_clear_returns_count(tmp_path):
    db = _provider(tmp_path)
    store = PositionStore(db)
    assert store.clear() == 0  # empty (table created on demand)

    store.upsert("o1", _POS)
    store.upsert("o2", _POS)
    assert store.clear() == 2
    assert store.count() == 0


def test_clear_circuit_state_reports_existence(tmp_path):
    db = _provider(tmp_path)
    assert clear_circuit_state(db) is False  # nothing persisted yet

    save_circuit_state(db, 123.0, 3, -12.0)
    assert load_circuit_state(db) is not None
    assert clear_circuit_state(db) is True
    assert load_circuit_state(db) is None  # breaker reloads CLOSED


# --------------------------------------------------------------- reset_paper_state
def test_reset_clears_breaker_and_positions(tmp_path):
    db = _provider(tmp_path)
    PositionStore(db).upsert("o1", _POS)
    save_circuit_state(db, 123.0, 6, -74.5)

    result = reset_paper_state(db)
    assert result["positions_before"] == 1
    assert result["breaker_before"]["daily_loss_pct"] == -74.5
    assert result["positions_cleared"] == 1
    assert result["breaker_cleared"] is True

    assert PositionStore(db).count() == 0
    assert load_circuit_state(db) is None


def test_dry_run_reports_but_changes_nothing(tmp_path):
    db = _provider(tmp_path)
    PositionStore(db).upsert("o1", _POS)
    save_circuit_state(db, 123.0, 6, -74.5)

    result = reset_paper_state(db, dry_run=True)
    assert result["dry_run"] is True
    assert result["positions_cleared"] == 1  # what WOULD be removed
    assert result["breaker_cleared"] is True

    # ...but the state is untouched.
    assert PositionStore(db).count() == 1
    assert load_circuit_state(db) is not None


def test_reset_on_clean_state_is_a_noop(tmp_path):
    db = _provider(tmp_path)
    result = reset_paper_state(db)
    assert result["positions_before"] == 0
    assert result["breaker_before"] is None
    assert result["positions_cleared"] == 0
    assert result["breaker_cleared"] is False
