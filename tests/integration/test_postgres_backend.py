"""PostgreSQL backend integration — runs only when DATABASE_URL points at Postgres.

Skipped in CI (no Postgres service). Run locally against a Postgres server:

    DATABASE_URL=postgresql://ct@localhost:5433/criptotrade EXCHANGE_DRY_RUN=true \
      python -m pytest tests/integration/test_postgres_backend.py -o addopts=''

The SQLite suite remains the default; this proves the same call sites work on
Postgres (placeholders, hybrid rows, upserts, autoincrement, RETURNING).
"""
from __future__ import annotations

import os

import pytest

_PG = os.getenv("DATABASE_URL", "").startswith(("postgres://", "postgresql://"))
pytestmark = pytest.mark.skipif(not _PG, reason="DATABASE_URL not set to Postgres")

from src.core.db import connection, init_db, is_postgres, upsert  # noqa: E402

_TABLES = [
    "orders", "cycle_events", "journal_entries", "backtest_jobs",
    "open_positions", "circuit_breaker_state", "ledger_events", "schema_migrations",
]


@pytest.fixture(autouse=True)
def _clean_schema():
    with connection() as conn:
        for table in _TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    init_db()
    yield


def test_backend_is_postgres():
    assert is_postgres() is True


def test_migrations_idempotent():
    assert init_db() == []  # fixture already applied them


def test_hybrid_row_positional_and_mapping():
    with connection() as conn:
        upsert(
            conn, "open_positions",
            ["order_id", "symbol", "side", "entry_price", "quantity",
             "stop_loss", "take_profit", "opened_at"],
            ("o1", "BTC/USDT", "buy", 100.0, 1.0, 95.0, 115.0, "t"),
            conflict="order_id",
        )
        row = conn.execute(
            "SELECT order_id, symbol FROM open_positions WHERE order_id=?", ("o1",)
        ).fetchone()
        assert row[0] == "o1"                  # positional (like sqlite3.Row)
        assert row["symbol"] == "BTC/USDT"     # mapping
        assert dict(row)["order_id"] == "o1"   # dict(row)
        assert conn.execute("SELECT COUNT(*) FROM open_positions").fetchone()[0] == 1


def test_ledger_roundtrip():
    from src.core.ledger import TradingLedger

    led = TradingLedger()
    led.log_decision("position_closed", {"symbol": "BTC/USDT", "pnl": 10.0})
    assert len(led.get_events("position_closed")) == 1
    assert led.read_all()[-1]["data"]["pnl"] == 10.0


def test_position_store_upsert_replace_delete_and_circuit_state():
    from src.orchestration.position_store import (
        PositionStore, load_circuit_state, save_circuit_state,
    )

    ps = PositionStore(lambda: "ignored-on-pg")
    pos = {"symbol": "BTC/USDT", "side": "buy", "entry_price": 100.0, "quantity": 1.0,
           "stop_loss": 95.0, "take_profit": 115.0, "opened_at": "t"}
    ps.upsert("o1", pos)
    assert ps.load_all()["o1"]["entry_price"] == 100.0
    ps.upsert("o1", {**pos, "entry_price": 101.0})  # ON CONFLICT DO UPDATE
    assert ps.load_all()["o1"]["entry_price"] == 101.0
    ps.delete("o1")
    assert ps.load_all() == {}

    save_circuit_state(lambda: "x", 123.0, 2, -3.5)
    assert load_circuit_state(lambda: "x") == {
        "tripped_at": 123.0, "consecutive_losses": 2, "daily_loss_pct": -3.5,
    }


def test_agent_registry_cycles_cross_process():
    from src.agents.registry import AgentRegistry

    reg = AgentRegistry(db_path="pg")  # non-None path enables DB mode; ignored on PG
    reg.record_cycle("strategy")
    reg.record_cycle("strategy")
    assert reg.cycles_today("strategy") == 2


def test_order_store_submit_pending_and_auto_fill():
    from src.core.ledger import TradingLedger
    from src.hitl.orders import Order, OrderStatus, OrderStore

    def _order():
        return Order(pair="BTC/USDT", side="buy", quantity=0.001, price=50000.0,
                     strategy="dca", agent_id="strategy", confidence=0.9, reason="r")

    manual = OrderStore(TradingLedger(), threshold_provider=lambda: 0.0, db_path="pg")
    assert manual.submit(_order()).status == OrderStatus.pending  # INSERT path

    auto = OrderStore(TradingLedger(), threshold_provider=lambda: 1e9, db_path="pg")
    assert auto.submit(_order()).status == OrderStatus.filled     # INSERT + UPDATE path
    assert auto.count() == 2


def test_journal_insert_returning_id():
    # The journal route uses RETURNING id on Postgres (no lastrowid).
    from fastapi.testclient import TestClient

    from src.api.main import create_app

    client = TestClient(create_app())
    resp = client.post("/v1/journal", json={
        "setup": "breakout", "emotion_before": 6, "emotion_after": 7,
        "stop_defined": True, "plan_followed": True, "pnl_pct": 1.2, "note": "ok",
    })
    assert resp.status_code == 201
    assert resp.json()["data"]["id"] >= 1
