"""Operational reset of the paper breaker + open-position book + orders.

Covers the store helpers (``PositionStore.clear`` / ``clear_circuit_state`` /
``OrderStore.clear``) and the ``reset_paper_state`` orchestration across BOTH
surfaces (ledger-db breaker/book + app-db orders), including the ``--dry-run``
contract (reports what *would* change, writes nothing) and the invariant that the
audit trail (``ledger_events``) is left intact.
"""
from __future__ import annotations

from scripts.reset_paper_state import main as reset_main
from scripts.reset_paper_state import reset_paper_state
from src.core.ledger import TradingLedger
from src.hitl.orders import Order, OrderStore
from src.orchestration.position_store import (
    PositionStore,
    clear_circuit_state,
    load_circuit_state,
    save_circuit_state,
)

_POS = {
    "symbol": "BTC/USDT", "side": "buy", "entry_price": 100.0, "quantity": 0.5,
    "stop_loss": 95.0, "take_profit": 115.0, "opened_at": "2026-01-01T00:00:00+00:00",
}


def _provider(tmp_path):
    ledger = TradingLedger(tmp_path / "trades.jsonl")

    def db():
        return ledger.db_path

    return db


def _order_store(tmp_path, ledger):
    # No auto-approval (threshold 0) so submitted orders stay as inserted rows.
    return OrderStore(ledger, threshold_provider=lambda: 0.0, db_path=str(tmp_path / "app.db"))


def _mk_order(pair="BTC/USDT"):
    return Order(pair=pair, side="buy", quantity=0.001, price=50_000.0, strategy="grid",
                 agent_id="strategy_agent", confidence=0.0, reason="stub")


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
    assert result["orders_cleared"] == 0  # no order_store passed → orders untouched


# --------------------------------------------------------- orders (2nd surface)
def test_order_store_clear_returns_count_and_preserves_ledger(tmp_path):
    ledger = TradingLedger(tmp_path / "trades.jsonl")
    store = _order_store(tmp_path, ledger)
    ledger.log_decision("position_closed", {"order_id": "audit", "pnl": 1.0})  # audit trail
    assert store.clear() == 0  # empty

    store.submit(_mk_order())
    store.submit(_mk_order("ETH/USDT"))
    assert store.count() == 2
    assert store.clear() == 2
    assert store.count() == 0
    # clear() hits the app-db orders table, NOT the ledger audit trail (a different
    # db): the seeded ledger_events row survives.
    assert len(ledger.get_events("position_closed")) == 1


def test_reset_clears_orders_and_preserves_audit_trail(tmp_path):
    ledger = TradingLedger(tmp_path / "trades.jsonl")

    def db():
        return ledger.db_path

    PositionStore(db).upsert("o1", _POS)
    save_circuit_state(db, 123.0, 6, -74.5)
    store = _order_store(tmp_path, ledger)
    store.submit(_mk_order())
    store.submit(_mk_order("ETH/USDT"))
    # an audit event that MUST survive the reset (never touched — it is the trail).
    ledger.log_decision("position_closed", {"order_id": "x", "pnl": -10.0})

    result = reset_paper_state(db, order_store=store)
    assert result["orders_before"] == 2 and result["orders_cleared"] == 2
    assert result["positions_cleared"] == 1 and result["breaker_cleared"] is True

    assert store.count() == 0
    assert PositionStore(db).count() == 0
    assert load_circuit_state(db) is None
    # ledger_events untouched — the whole point of the "operational only" reset.
    assert len(ledger.get_events("position_closed")) == 1


def test_dry_run_reports_orders_but_changes_nothing(tmp_path):
    ledger = TradingLedger(tmp_path / "trades.jsonl")

    def db():
        return ledger.db_path

    store = _order_store(tmp_path, ledger)
    store.submit(_mk_order())

    result = reset_paper_state(db, order_store=store, dry_run=True)
    assert result["dry_run"] is True
    assert result["orders_cleared"] == 1  # what WOULD be removed
    assert store.count() == 1  # ...but untouched


# --------------------------------------------------------------------- main() CLI
# M4: o ledger db E o app db derivam de LEDGER_DIR (get_db_path), então apontá-lo ao
# tmp isola os dois; main() lê esse mesmo estado.
def _seed_dirty(monkeypatch, tmp_path):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    ledger = TradingLedger()

    def db():
        return ledger.db_path

    PositionStore(db).upsert("o1", _POS)
    save_circuit_state(db, 123.0, 6, -74.5)
    return db


def test_main_yes_resets_without_prompting(tmp_path, monkeypatch):
    db = _seed_dirty(monkeypatch, tmp_path)

    def _no_input(*_a, **_k):
        raise AssertionError("input() não deve ser chamado com --yes")

    monkeypatch.setattr("builtins.input", _no_input)
    assert reset_main(["--yes"]) == 0
    assert PositionStore(db).count() == 0
    assert load_circuit_state(db) is None


def test_main_eof_without_yes_aborts_cleanly(tmp_path, monkeypatch):
    # M4: sem --yes e sem TTY (docker exec sem -it), input() levanta EOFError — o
    # script deve abortar limpo (return 1, sem traceback) e NÃO tocar o estado.
    db = _seed_dirty(monkeypatch, tmp_path)

    def _raise_eof(*_a, **_k):
        raise EOFError

    monkeypatch.setattr("builtins.input", _raise_eof)
    assert reset_main([]) == 1
    assert PositionStore(db).count() == 1
    assert load_circuit_state(db) is not None
