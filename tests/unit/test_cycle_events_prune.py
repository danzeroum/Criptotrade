"""Fase 5b: cycle_events pruning keeps the cross-process table bounded."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.agents.registry import AgentRegistry
from src.core.db import connection


def _count(db_path: str) -> int:
    with connection(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM cycle_events").fetchone()[0]


def test_prune_cycle_events_drops_only_old_rows(tmp_path):
    db = str(tmp_path / "agents.db")
    reg = AgentRegistry(db_path=db)
    now = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)
    reg.record_cycle("a1", when=now - timedelta(days=40))  # stale → pruned
    reg.record_cycle("a1", when=now - timedelta(days=5))   # within retention
    reg.record_cycle("a2", when=now)                       # today
    assert _count(db) == 3

    deleted = reg.prune_cycle_events(retention_days=30, now=now)

    assert deleted == 1
    assert _count(db) == 2


def test_prune_cycle_events_is_noop_without_db():
    # An in-memory registry (no db_path) must be a safe no-op.
    assert AgentRegistry().prune_cycle_events() == 0
