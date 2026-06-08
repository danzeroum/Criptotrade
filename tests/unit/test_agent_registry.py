"""Phase 4b-ii — AgentRegistry in-memory cycle aggregation (no file scan)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.agents.registry import AGENT_PARAMS, AGENT_REGISTRY, AgentRegistry


def test_record_cycle_increments_in_memory():
    reg = AgentRegistry()
    reg.record_cycle("strategy")
    reg.record_cycle("strategy")
    reg.record_cycle("risk")
    assert reg.status("strategy")["cycles"] == 2
    assert reg.status("risk")["cycles"] == 1
    assert reg.status("strategy")["last_action_at"] is not None


def test_cycles_never_scan_the_ledger():
    # A ledger whose read is fatal: if the registry touched it, this would blow up.
    class _ExplodingLedger:
        def read_all(self):
            raise AssertionError("registry must not scan the ledger for cycles")

        def get_events(self, *_a, **_k):
            raise AssertionError("registry must not scan the ledger for cycles")

    # Passing a ledger is deprecated (ignored) — and must not be scanned.
    with pytest.warns(DeprecationWarning):
        reg = AgentRegistry(_ExplodingLedger())
    for _ in range(1000):
        reg.record_cycle("strategy")
    assert reg.status("strategy")["cycles"] == 1000  # O(1), no file access


def test_no_ledger_does_not_warn(recwarn):
    AgentRegistry()
    assert not any(issubclass(w.category, DeprecationWarning) for w in recwarn)


def test_cycles_reset_on_new_utc_day():
    reg = AgentRegistry()
    # Use today's 23:59 UTC so day1.date() == _cycles_date (today) and
    # day2 = day1 + 1h falls on the next UTC day, triggering the reset.
    now = datetime.now(timezone.utc)
    day1 = now.replace(hour=23, minute=59, second=0, microsecond=0)
    reg.record_cycle("strategy", when=day1)
    reg.record_cycle("strategy", when=day1)
    assert reg.status("strategy")["cycles"] == 2

    # First event of the next UTC day resets the counters.
    day2 = day1 + timedelta(hours=1)
    reg.record_cycle("strategy", when=day2)
    assert reg.status("strategy")["cycles"] == 1


def test_unknown_agent_status_is_none():
    assert AgentRegistry().status("nope") is None


def test_unrecorded_agent_has_zero_cycles():
    reg = AgentRegistry()
    s = reg.status("architect")
    assert s["cycles"] == 0
    assert s["last_action_at"] is None


def test_stub_agents_flagged_not_implemented():
    reg = AgentRegistry()
    assert reg.status("recovery")["status"] == "not_implemented"
    assert reg.status("strategy")["status"] == "idle"


# ----------------------------------------------------------- 5a-iii cross-process
def test_cross_process_cycles_via_shared_db(tmp_path):
    db = str(tmp_path / "agents.db")
    loop_reg = AgentRegistry(db_path=db)   # the loop writes
    api_reg = AgentRegistry(db_path=db)    # the API reads (separate instance)

    for _ in range(3):
        loop_reg.record_cycle("strategy")

    assert api_reg.cycles_today("strategy") == 3
    assert api_reg.status("strategy")["cycles"] == 3
    assert api_reg.status("strategy")["last_action_at"] is not None


def test_no_db_path_is_legacy_in_memory(tmp_path):
    reg = AgentRegistry()  # no db_path -> pure in-memory, no SQLite touched
    reg.record_cycle("strategy")
    assert reg.cycles_today("strategy") == 1
    # A second registry without a shared db sees nothing — confirms it's local.
    assert AgentRegistry().cycles_today("strategy") == 0


def test_cycles_today_counts_only_current_utc_day(tmp_path):
    reg = AgentRegistry(db_path=str(tmp_path / "agents.db"))
    now = datetime.now(timezone.utc)
    reg.record_cycle("strategy", when=now)
    reg.record_cycle("strategy", when=now - timedelta(days=2))  # previous day
    assert reg.cycles_today("strategy") == 1


# ----------------------------------------------------------- AGENT_PARAMS integrity
def test_agent_params_covers_all_registered_agents():
    """Every agent in AGENT_REGISTRY must have an entry in AGENT_PARAMS."""
    registry_ids = set(AGENT_REGISTRY.keys())
    params_ids = set(AGENT_PARAMS.keys())
    assert registry_ids == params_ids, (
        f"AGENT_PARAMS mismatch — only in registry: {registry_ids - params_ids}, "
        f"only in params: {params_ids - registry_ids}"
    )


def test_implemented_agents_have_autonomy_level():
    """Every implemented agent must declare autonomy_level in AGENT_PARAMS."""
    for agent_id, info in AGENT_REGISTRY.items():
        if info.implemented:
            assert "autonomy_level" in AGENT_PARAMS[agent_id], (
                f"Agent '{agent_id}' is implemented but missing 'autonomy_level' in AGENT_PARAMS"
            )


def test_stub_agents_have_empty_params():
    """Stub agents (not implemented) must have empty AGENT_PARAMS (no false data)."""
    for agent_id, info in AGENT_REGISTRY.items():
        if not info.implemented:
            assert AGENT_PARAMS[agent_id] == {}, (
                f"Stub agent '{agent_id}' should have empty params, got: {AGENT_PARAMS[agent_id]}"
            )
