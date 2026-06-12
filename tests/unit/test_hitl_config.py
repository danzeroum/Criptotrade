"""Tests for HITLConfigStore and related helpers in src/hitl/config.py."""
from __future__ import annotations

import pytest

from src.core.ledger import TradingLedger
from src.hitl.config import (
    DEFAULT_LEVEL,
    HITLConfigStore,
    level_from_env,
    level_info,
)


# ── level_info ────────────────────────────────────────────────────────────────

def test_level_info_returns_correct_thresholds():
    assert level_info(0).threshold_usdt == 0.0
    assert level_info(1).threshold_usdt == 500.0
    assert level_info(2).threshold_usdt == 1_000.0
    assert level_info(3).threshold_usdt == 5_000.0


def test_level_info_invalid_raises():
    with pytest.raises(ValueError, match="Autonomy level"):
        level_info(-1)
    with pytest.raises(ValueError, match="Autonomy level"):
        level_info(4)


# ── level_from_env ────────────────────────────────────────────────────────────

def test_level_from_env_not_set_returns_default(monkeypatch):
    monkeypatch.delenv("AUTONOMY_LEVEL", raising=False)
    assert level_from_env() == DEFAULT_LEVEL


def test_level_from_env_valid_int(monkeypatch):
    monkeypatch.setenv("AUTONOMY_LEVEL", "1")
    assert level_from_env() == 1


def test_level_from_env_non_int_returns_default(monkeypatch):
    monkeypatch.setenv("AUTONOMY_LEVEL", "not_a_number")
    assert level_from_env() == DEFAULT_LEVEL


def test_level_from_env_out_of_range_returns_default(monkeypatch):
    monkeypatch.setenv("AUTONOMY_LEVEL", "99")
    assert level_from_env() == DEFAULT_LEVEL


# ── HITLConfigStore ───────────────────────────────────────────────────────────

@pytest.fixture
def ledger(tmp_path):
    return TradingLedger(tmp_path / "trades.jsonl")


def test_set_level_valid(ledger):
    store = HITLConfigStore(ledger, initial_level=2)
    store.set_level(1, reason="risk reduction", operator="admin")
    assert store.level == 1


def test_set_level_short_reason_raises(ledger):
    store = HITLConfigStore(ledger)
    with pytest.raises(ValueError, match="reason"):
        store.set_level(1, reason="tiny", operator="admin")


def test_snapshot_returns_required_keys(ledger):
    store = HITLConfigStore(ledger, initial_level=2)
    snap = store.snapshot()
    for key in ("current_level", "threshold_usdt", "pending_orders_count", "levels"):
        assert key in snap


def test_snapshot_pending_without_provider_uses_ledger(ledger):
    """Without a pending_orders_provider, _pending_orders_count is called."""
    store = HITLConfigStore(ledger, initial_level=2)
    # pending_orders_provider is None by default → covers lines 168-170
    snap = store.snapshot()
    assert snap["pending_orders_count"] == 0


def test_snapshot_counts_approvals_from_ledger(ledger):
    """Seeding hitl_approval events covers the _count_today body (lines 149-159)."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    # Log one approved and one rejected today
    ledger.log_decision("hitl_approval", {"approved": True, "order_id": "a1"})
    ledger.log_decision("hitl_approval", {"approved": False, "order_id": "a2"})

    store = HITLConfigStore(ledger, initial_level=2)
    snap = store.snapshot(now=now)
    assert snap["human_approved_today"] == 1
    assert snap["human_rejected_today"] == 1


def test_snapshot_ignores_approvals_from_other_days(ledger):
    """Approvals logged today are not counted when snapshot uses a different date."""
    from datetime import datetime, timezone
    # Log an approval now (actual current timestamp)
    ledger.log_decision("hitl_approval", {"approved": True, "order_id": "b1"})
    store = HITLConfigStore(ledger, initial_level=2)
    # Ask for the snapshot using a reference date far in the past
    past = datetime(2020, 1, 1, tzinfo=timezone.utc)
    snap = store.snapshot(now=past)
    # Today's count (for 2020-01-01) should be zero — events were logged in 2026
    assert snap["human_approved_today"] == 0


def test_snapshot_with_pending_provider(ledger):
    store = HITLConfigStore(ledger, initial_level=2)
    store.pending_orders_provider = lambda: 5
    assert store.snapshot()["pending_orders_count"] == 5
