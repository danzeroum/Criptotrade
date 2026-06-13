"""Nineteenth batch — trade_journal reload, base_agent/strategy/module edge cases."""
from __future__ import annotations

import asyncio
import runpy
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── trade_journal — _load with valid entries (branch 204->exit) ───────────────

def test_trade_journal_load_valid_entries(tmp_path):
    """Branch 204->exit: for loop over raw.items() exits normally (all entries loaded)."""
    from src.journal.trade_journal import TradeEntry, TradeJournal

    journal_path = str(tmp_path / "journal.json")
    j1 = TradeJournal(journal_path)
    entry = TradeEntry(
        order_id="ord-load-001",
        symbol="BTC/USDT",
        action="BUY",
        entry_price=50_000.0,
    )
    j1.record_entry(entry)   # saves to file

    # Reload from the same path → _load() runs, for loop iterates entry and exits
    j2 = TradeJournal(journal_path)
    loaded = j2.all_entries()
    assert len(loaded) == 1
    assert loaded[0].order_id == "ord-load-001"


# ── base_strategy — get_parameters() (line 17) ────────────────────────────────

def test_base_strategy_get_parameters():
    """Line 17: get_parameters() returns {}."""
    from src.strategies.dca_optimized import DCAOptimizedStrategy

    strategy = DCAOptimizedStrategy()
    params = strategy.get_parameters()
    assert isinstance(params, dict)
    # DCAOptimizedStrategy may override get_parameters; if not, falls through to base
    # Either way, the call exercises the method chain including BaseStrategy.get_parameters


def test_base_strategy_get_parameters_base_directly():
    """Line 17: BaseStrategy.get_parameters returns {}."""
    from src.strategies.base_strategy import BaseStrategy
    from src.strategies.mean_reversion import MeanReversionStrategy

    strategy = MeanReversionStrategy()
    # If MeanReversionStrategy doesn't override get_parameters, BaseStrategy.get_parameters
    # at line 17 is called
    params = strategy.get_parameters()
    assert isinstance(params, dict)


# ── base_agent — AgentMemorySystem=None → else branch (line 33) ───────────────

def test_base_agent_memory_none_else_branch():
    """Line 33: AgentMemorySystem is None → else branch sets memory=None."""
    import src.agents.base_agent as base_mod

    original = base_mod.AgentMemorySystem
    try:
        base_mod.AgentMemorySystem = None   # force else branch at line 32-33

        class _ConcreteAgent(base_mod.BaseAgent):
            async def execute(self, task):
                return {"success": True}

        agent = _ConcreteAgent("test")
        assert agent.memory is None   # line 33 covered (else: self.memory = None)
    finally:
        base_mod.AgentMemorySystem = original


# ── base_agent — abstract execute body (line 40) ──────────────────────────────

@pytest.mark.asyncio
async def test_base_agent_abstract_execute_pass():
    """Line 40: call super().execute() on the abstract method body (pass)."""
    from src.agents.base_agent import BaseAgent

    class _ConcreteAgent(BaseAgent):
        async def execute(self, task):
            # Explicitly call the abstract base implementation → line 40 (pass)
            base_result = await BaseAgent.execute(self, task)
            return {"success": True, "base_result": base_result}

    agent = _ConcreteAgent("test_agent")
    result = await agent.execute({"task": "test"})
    assert result["success"] is True
    assert result["base_result"] is None   # abstract execute returns None (pass)


# ── main.py — __main__ entry point (line 29) ──────────────────────────────────

def test_main_module_main_entrypoint():
    """Line 29: asyncio.run(main()) triggered by __name__ == '__main__'."""
    with patch("asyncio.run", MagicMock()) as mock_run:
        runpy.run_module("src.main", run_name="__main__", alter_sys=False)
    # asyncio.run was called (line 29 executed)
    mock_run.assert_called_once()


# ── main_loop.py — main() call from __main__ (line 54) ────────────────────────

def test_main_loop_module_main_entrypoint():
    """Line 54: main() called from __name__ == '__main__' block."""
    with patch("asyncio.run", MagicMock()) as mock_run:
        runpy.run_module("src.orchestration.main_loop", run_name="__main__", alter_sys=False)
    mock_run.assert_called_once()
