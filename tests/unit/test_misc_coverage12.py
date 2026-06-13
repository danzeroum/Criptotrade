"""Twelfth batch — memory, orchestrator, pattern scanner edge cases."""
from __future__ import annotations

import sys
import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch


# ── utils/memory_utils — snapshot() (line 22) ─────────────────────────────────

def test_memory_store_snapshot():
    """Line 22: snapshot() returns a copy of _storage."""
    from src.utils.memory_utils import MemoryStore

    store = MemoryStore()
    store.set("k1", "v1")
    store.set("k2", 42)
    snap = store.snapshot()
    assert snap == {"k1": "v1", "k2": 42}
    # Modifying snap doesn't affect store
    snap["k3"] = "extra"
    assert "k3" not in store._storage


# ── orchestrator — _prepare_context non-list/non-string (line 59) ─────────────

def test_orchestrator_prepare_context_non_list_non_string():
    """Line 59: retrieval_result is neither list nor str → returns None."""
    from src.orchestrator import AgentOrchestrator

    # Create a minimal AgentOrchestrator without needing vector_db_url to work
    with patch("src.orchestrator.SafeAgentBase"), \
         patch("src.orchestrator.ContinuousEvaluator"), \
         patch("src.orchestrator.RAGTool"), \
         patch("src.orchestrator.MCPServer"):
        orch = AgentOrchestrator.__new__(AgentOrchestrator)
        result = orch._prepare_context(42)      # int → falls through to return None
        assert result is None
        result2 = orch._prepare_context(None)   # NoneType → return None
        assert result2 is None


# ── agent_memory — chromadb available path (lines 9, 27, 31-35) ──────────────

def test_agent_memory_with_chromadb_available():
    """Lines 27, 31-35: CHROMADB_AVAILABLE=True → _init_vector_store() called."""
    # Patch chromadb into sys.modules and set CHROMADB_AVAILABLE
    mock_chromadb = MagicMock()
    mock_collection = MagicMock()
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    mock_chromadb.Client.return_value = mock_client

    with patch.dict(sys.modules, {"chromadb": mock_chromadb}):
        # Reload the module so CHROMADB_AVAILABLE is recomputed
        import importlib
        import src.memory.agent_memory as mem_mod
        importlib.reload(mem_mod)
        try:
            system = mem_mod.AgentMemorySystem()
            # _init_vector_store should have been called
            mock_chromadb.Client.assert_called()
        finally:
            # Reload without chromadb to restore the original state
            sys.modules.pop("chromadb", None)
            importlib.reload(mem_mod)


def test_agent_memory_chromadb_init_exception():
    """Lines 31-35: chromadb.Client() raises → collection stays None."""
    mock_chromadb = MagicMock()
    mock_chromadb.Client.side_effect = Exception("chromadb failure")

    with patch.dict(sys.modules, {"chromadb": mock_chromadb}):
        import importlib
        import src.memory.agent_memory as mem_mod
        importlib.reload(mem_mod)
        try:
            system = mem_mod.AgentMemorySystem()
            assert system.collection is None
        finally:
            sys.modules.pop("chromadb", None)
            importlib.reload(mem_mod)


def test_agent_memory_remember_with_collection():
    """Lines 50-57: collection not None → collection.add() called."""
    mock_chromadb = MagicMock()
    mock_collection = MagicMock()
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    mock_chromadb.Client.return_value = mock_client

    with patch.dict(sys.modules, {"chromadb": mock_chromadb}):
        import importlib
        import src.memory.agent_memory as mem_mod
        importlib.reload(mem_mod)
        try:
            system = mem_mod.AgentMemorySystem()
            system.remember_decision("agent1", {"action": "buy", "timestamp": "2026-01-01"})
            mock_collection.add.assert_called_once()
        finally:
            sys.modules.pop("chromadb", None)
            importlib.reload(mem_mod)


# ── pattern_scanner — head-and-shoulders branch conditions ────────────────────

def test_pattern_scanner_h_and_s_head_not_higher_than_shoulders():
    """Line 148 (continue): head NOT > both shoulders → continue."""
    from src.analysis.pattern_scanner import PatternScanner

    scanner = PatternScanner()
    # Directly test with crafted arrays:
    # pivot_highs = [0, 1, 2]: values [100, 90, 95] — head(90) < ls(100) → continue
    highs = np.array([100.0, 90.0, 95.0, 80.0, 85.0])
    lows  = np.array([ 95.0, 85.0, 88.0, 75.0, 80.0])
    closes = np.array([97.0, 88.0, 92.0, 78.0, 83.0])
    pivot_highs = [0, 1, 2]  # head=highs[1]=90 < ls=highs[0]=100 → line 148

    results = scanner._check_head_and_shoulders(highs, lows, closes, pivot_highs)
    # The triple fails condition → no result
    assert results == []


def test_pattern_scanner_h_and_s_unequal_shoulders():
    """Line 151 (continue): head > both shoulders but shoulders too unequal → continue."""
    from src.analysis.pattern_scanner import PatternScanner

    scanner = PatternScanner()
    # pivot_highs=[0,1,2]: ls=100, head=110, rs=94 → diff=|100-94|/100=0.06 > 0.03
    highs = np.array([100.0, 110.0, 94.0, 80.0, 85.0])
    lows  = np.array([ 95.0,  85.0, 88.0, 75.0, 80.0])
    closes = np.array([97.0, 108.0, 92.0, 78.0, 83.0])
    pivot_highs = [0, 1, 2]

    results = scanner._check_head_and_shoulders(highs, lows, closes, pivot_highs)
    # head(110) > ls(100) AND head(110) > rs(94), but |100-94|/100=0.06>0.03 → line 151
    assert results == []


# ── pattern_scanner — ascending triangle non-rising support (line 186) ────────

def test_pattern_scanner_ascending_triangle_flat_support():
    """Line 186: bot_b <= bot_a → non-rising support → return []."""
    from src.analysis.pattern_scanner import PatternScanner

    scanner = PatternScanner()
    n = 50
    highs  = np.full(n, 100.0)
    lows   = np.full(n, 90.0)  # flat lows: bot_b == bot_a → bot_b <= bot_a → line 186
    pivot_highs = [5, 25]   # flat tops: both = 100
    pivot_lows  = [10, 30]  # flat lows: both = 90

    results = scanner._check_ascending_triangle(highs, lows, pivot_highs, pivot_lows)
    assert results == []


# ── pattern_scanner — rectangle bearish breakout (lines 258-259) ──────────────

def test_pattern_scanner_rectangle_bearish():
    """Lines 258-259: current < support → bearish direction."""
    from src.analysis.pattern_scanner import PatternScanner

    scanner = PatternScanner()
    n = 50
    # Flat highs (resistance) ~100, flat lows (support) ~90
    # Current price below support: closes[-1] = 88 < 90 * 1.005 → bearish
    highs  = np.full(n, 100.0)
    lows   = np.full(n, 90.0)
    closes = np.concatenate([np.full(n - 1, 95.0), [88.0]])  # last candle below support
    pivot_highs = [5, 25]   # highs all 100: within 1.5% tolerance
    pivot_lows  = [10, 30]  # lows all 90: within 1.5% tolerance

    results = scanner._check_rectangle(highs, lows, closes, pivot_highs, pivot_lows)
    bearish = [r for r in results if r.direction == "bearish"]
    assert len(bearish) > 0


# ── squad_orchestrator — _check_open_positions exception path ────────────────

@pytest.mark.asyncio
async def test_squad_orchestrator_position_check_exception(tmp_path, monkeypatch):
    """Lines 174-175: _check_open_positions raises → exception caught, warn logged."""
    from src.orchestration.squad_orchestrator import SquadOrchestrator

    orch = SquadOrchestrator.__new__(SquadOrchestrator)
    orch.strategy_agent = MagicMock()
    orch.strategy_agent.execute = AsyncMock(return_value={
        "success": True,
        "signal": {
            "action": "BUY",
            "entry_price": 50_000.0,  # > 0 → triggers _check_open_positions
        },
        "confidence": 0.4,  # < 0.6 → returns early after exception handling
    })
    orch.ledger = MagicMock()
    orch.ledger.log_signal = MagicMock()
    orch.circuit_breaker = MagicMock()
    orch.circuit_breaker.is_open = False
    orch.alert_store = None
    orch.alert_bus = None
    orch._open_positions = {}
    orch.approval_handler = None
    orch.fill_callback = None
    orch._last_order_ref = None
    orch.initial_capital = 10_000.0

    def _check_raises(price, symbol):
        raise RuntimeError("position check failed intentionally")

    orch._check_open_positions = _check_raises

    # analyze_and_trade should NOT raise — exception is caught at line 174-175
    result = await orch.analyze_and_trade(symbol="BTC/USDT")
    assert isinstance(result, dict)


# ── unified_orchestrator — _attempt_recovery (lines 192-194) ─────────────────

@pytest.mark.asyncio
async def test_unified_orchestrator_attempt_recovery():
    """Lines 192-194: _attempt_recovery calls execute_complex_task with simplified task."""
    from src.orchestration.unified_orchestrator import UnifiedOrchestrator

    orch = UnifiedOrchestrator.__new__(UnifiedOrchestrator)

    recovered = {"success": True, "task_id": "recovery"}
    orch.execute_complex_task = AsyncMock(return_value=recovered)

    task = {"description": "original complex task"}
    result = await orch._attempt_recovery(task, "some error")
    assert result == recovered

    # Verify simplified task was passed
    call_args = orch.execute_complex_task.call_args[0][0]
    assert call_args["simplified"] is True
    assert call_args["priority"] == "low"


# ── unified_orchestrator — low quality replanning (lines 151-152) ─────────────

@pytest.mark.asyncio
async def test_unified_orchestrator_low_quality_replan():
    """Lines 151-152: technical_score < 0.6 → replan_from_point called."""
    from src.orchestration.unified_orchestrator import UnifiedOrchestrator

    orch = UnifiedOrchestrator.__new__(UnifiedOrchestrator)
    orch.agents = {
        # "validate" → "auditor" (sequential, not parallelized)
        "auditor": MagicMock(execute=AsyncMock(return_value={"success": True})),
    }
    orch.evaluator = MagicMock()
    orch.evaluator.evaluate_agent_performance = AsyncMock(
        return_value={"technical_score": 0.3}  # < 0.6 → triggers replanning
    )
    orch.planner = MagicMock()
    orch.planner.replan_from_point = AsyncMock(return_value={"steps": []})

    # action="validate" → _can_parallelize returns False (sequential path)
    plan = {"steps": [
        {"step": 1, "action": "validate", "description": "validate it"},
    ]}
    await orch._execute_plan_steps(plan, {"description": "test task"})

    orch.planner.replan_from_point.assert_awaited_once()
