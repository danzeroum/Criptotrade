"""Orchestrator loop heartbeat (v3 operability)."""
from __future__ import annotations

import time

from src.orchestration.heartbeat import is_fresh, read_heartbeat, write_heartbeat


def test_write_read_roundtrip(tmp_path):
    p = tmp_path / "loop_heartbeat.json"
    write_heartbeat(p, "cycle_1")
    hb = read_heartbeat(p)
    assert hb["cycle_id"] == "cycle_1"
    assert "ts" in hb


def test_is_fresh_true_for_recent(tmp_path):
    p = tmp_path / "loop_heartbeat.json"
    write_heartbeat(p, "c")
    assert is_fresh(read_heartbeat(p), max_age_seconds=60) is True


def test_is_fresh_false_for_stale():
    assert is_fresh({"ts": time.time() - 1000}, max_age_seconds=60) is False


def test_is_fresh_false_for_missing_or_malformed():
    assert is_fresh(None, 60) is False
    assert is_fresh({}, 60) is False
    assert is_fresh({"ts": "not-a-number"}, 60) is False


def test_read_missing_returns_none(tmp_path):
    assert read_heartbeat(tmp_path / "nope.json") is None
