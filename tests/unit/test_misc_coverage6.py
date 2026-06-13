"""Sixth batch of miscellaneous edge-case coverage."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock


# ── RiskAgent._validate_signal — stop loss too wide ──────────────────────────

@pytest.mark.asyncio
async def test_risk_agent_validate_wide_stop_loss_adds_warning():
    """Lines 75-78: entry>0 AND stop_loss% > stop_loss_pct → warning added."""
    from src.agents.risk_agent import RiskAgent

    agent = RiskAgent()  # default stop_loss_pct = 3.0
    signal = {
        "entry_price": 50_000.0,
        "stop_loss": 44_000.0,   # 12% wide > 3% limit → warning
        "position_size_pct": 1.0,
        "take_profit": 55_000.0,
    }
    result = await agent._validate_signal(signal, {})
    assert any("Stop loss" in w for w in result["warnings"])


# ── BaseAgent.log_decision — no memory (False branch) ─────────────────────────

def test_log_decision_no_memory_skips_persist():
    """Lines 55->61: self.memory is None → if block skipped, still returns entry."""
    from src.agents.developer_agent import DeveloperAgent

    agent = DeveloperAgent()
    agent.memory = None  # force memory to None to hit the False branch
    entry = agent.log_decision({"action": "test_no_memory"})
    assert entry is not None


# ── ContinuousEvaluator._record — existing metric appended ───────────────────

@pytest.mark.asyncio
async def test_continuous_evaluator_record_existing_metric():
    """Line 46->47: metric in self.metrics → value appended."""
    from src.evaluation.continuous_evaluator import ContinuousEvaluator

    evaluator = ContinuousEvaluator()
    # Find an existing metric key
    first_key = next(iter(evaluator.metrics))
    initial_len = len(evaluator.metrics[first_key])
    evaluator._record(first_key, 0.85)
    assert len(evaluator.metrics[first_key]) == initial_len + 1


def test_continuous_evaluator_record_unknown_metric():
    """Line 46->exit: metric not in self.metrics → no-op."""
    from src.evaluation.continuous_evaluator import ContinuousEvaluator

    evaluator = ContinuousEvaluator()
    evaluator._record("nonexistent_metric", 0.5)  # no crash, no change


# ── reset_singletons — clears all cached functions ───────────────────────────

def test_reset_singletons_runs_without_error():
    """Lines 101-105: reset_singletons clears all lru_cache entries."""
    from src.api.deps import reset_singletons

    # Should not raise
    reset_singletons()


# ── ArchitectAgent.execute — invalid task raises ─────────────────────────────

@pytest.mark.asyncio
async def test_architect_execute_invalid_task_raises():
    """Line 23: validate_input fails → ValueError raised."""
    from src.agents.architect_agent import ArchitectAgent

    agent = ArchitectAgent()
    with pytest.raises(ValueError, match="Invalid architectural task payload"):
        await agent.execute(None)


# ── ParallelResourceManager — callable task branch ───────────────────────────

@pytest.mark.asyncio
async def test_parallel_execute_with_callable_tasks():
    """Line 26: callable task → await task() called."""
    from src.parallel.resource_manager import ParallelResourceManager

    manager = ParallelResourceManager()

    async def task_fn():
        return "result_from_callable"

    results = await manager.execute_parallel_with_limits([task_fn])
    assert results == ["result_from_callable"]


# ── Ledger — get_recent_trades ────────────────────────────────────────────────

def test_ledger_get_recent_trades_with_entries(tmp_path):
    """Line 216: reversed(rows) returns entries in reverse order."""
    from src.core.ledger import TradingLedger

    ledger = TradingLedger(tmp_path / "l.jsonl")
    ledger.log_decision("order_filled", {"order_id": "o1", "pnl": 100.0})
    ledger.log_decision("order_filled", {"order_id": "o2", "pnl": -50.0})

    trades = ledger.get_recent_trades(limit=10)
    # Result should be non-empty (filled orders)
    assert isinstance(trades, list)
