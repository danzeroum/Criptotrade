"""Phase 5a-i — SQLite backend: connection PRAGMAs + migration runner."""
from __future__ import annotations

import sqlite3

import pytest

from src.core.db import MIGRATIONS_DIR, connection, init_db


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "criptotrade.db"
    init_db(db_path=path, migrations_dir=MIGRATIONS_DIR)
    return path


# ----------------------------------------------------------------- connection
def test_connection_sets_pragmas(tmp_path):
    path = tmp_path / "t.db"
    with connection(path) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_connection_rolls_back_on_error(tmp_path):
    path = tmp_path / "t.db"
    init_db(db_path=path)
    with pytest.raises(RuntimeError):
        with connection(path) as conn:
            conn.execute(
                "INSERT INTO cycle_events(agent_id, cycled_at) VALUES ('x', '2026-06-04')"
            )
            raise RuntimeError("boom")
    with connection(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM cycle_events").fetchone()[0] == 0


# ----------------------------------------------------------------- migrations
def test_init_db_creates_tables(db):
    with connection(db) as conn:
        tables = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert {"orders", "cycle_events", "schema_migrations"} <= tables


def test_init_db_is_idempotent(tmp_path):
    path = tmp_path / "c.db"
    first = init_db(db_path=path)
    second = init_db(db_path=path)
    assert "001_orders_and_cycles.sql" in first
    assert second == []  # nothing re-applied


def test_indexes_exist(db):
    with connection(db) as conn:
        idx = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert "idx_orders_status" in idx
    assert "idx_cycle_agent_day" in idx


# ----------------------------------------------------------------- constraints
def test_orders_status_check_rejects_invalid(db):
    with pytest.raises(sqlite3.IntegrityError):
        with connection(db) as conn:
            conn.execute(
                "INSERT INTO orders(id, pair, side, quantity, price, status, created_at) "
                "VALUES ('ord_1','BTC/USDT','buy',1,100,'bogus','2026-06-04T00:00:00Z')"
            )


def test_orders_accepts_approved_status(db):
    # 'approved' is the cross-process intermediate (API decides, loop fills).
    with connection(db) as conn:
        conn.execute(
            "INSERT INTO orders(id, pair, side, quantity, price, status, created_at) "
            "VALUES ('ord_2','BTC/USDT','buy',1,100,'approved','2026-06-04T00:00:00Z')"
        )
    with connection(db) as conn:
        row = conn.execute("SELECT status FROM orders WHERE id='ord_2'").fetchone()
        assert row[0] == "approved"


def test_orders_quantity_must_be_positive(db):
    with pytest.raises(sqlite3.IntegrityError):
        with connection(db) as conn:
            conn.execute(
                "INSERT INTO orders(id, pair, side, quantity, price, status, created_at) "
                "VALUES ('ord_3','BTC/USDT','buy',0,100,'pending','2026-06-04T00:00:00Z')"
            )


# ----------------------------------------------------------------- cycles query
def test_cycle_events_count_by_agent_and_day(db):
    rows = [
        ("strategy", "2026-06-04T10:00:00+00:00"),
        ("strategy", "2026-06-04T11:00:00+00:00"),
        ("strategy", "2026-06-03T11:00:00+00:00"),  # previous day
        ("risk", "2026-06-04T10:00:00+00:00"),
    ]
    with connection(db) as conn:
        conn.executemany("INSERT INTO cycle_events(agent_id, cycled_at) VALUES (?,?)", rows)
    with connection(db) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM cycle_events WHERE agent_id=? AND cycled_at >= ?",
            ("strategy", "2026-06-04T00:00:00+00:00"),
        ).fetchone()[0]
    assert count == 2  # today's strategy cycles only
