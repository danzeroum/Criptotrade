"""Fifteenth batch — adaptive planner, evaluator, voting, agents, backtest, orchestrators."""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── adaptive_planner — create_adaptive_plan high priority + high complexity ────

@pytest.mark.asyncio
async def test_adaptive_planner_create_plan_high_priority():
    """Lines 21-84: high priority + high complexity → design step + long duration."""
    from src.planning.adaptive_planner import AdaptivePlanner

    planner = AdaptivePlanner()
    task = {"description": "Build microservices", "priority": "high", "complexity": "high"}
    plan = await planner.create_adaptive_plan(task)

    assert plan["goal"] == "Build microservices"
    assert plan["adaptive"] is True
    actions = [s["action"] for s in plan["steps"]]
    assert "design" in actions          # priority="high" branch (line 45-55)
    # high priority → *1.5, high complexity → *2 → 60*1.5*2=180
    assert plan["estimated_duration"] == 180
    # duration 180 > 120 → confidence -= 0.1; 4 steps not >5 → no second deduct
    assert plan["confidence"] <= 0.75
    assert plan in planner.plan_history


@pytest.mark.asyncio
async def test_adaptive_planner_create_plan_normal_priority():
    """Lines 78-84: default priority/complexity → no design step, base duration."""
    from src.planning.adaptive_planner import AdaptivePlanner

    planner = AdaptivePlanner()
    plan = await planner.create_adaptive_plan({"description": "Simple fix"})

    actions = [s["action"] for s in plan["steps"]]
    assert "design" not in actions
    assert plan["estimated_duration"] == 60


# ── adaptive_planner — replan_from_point (lines 94-148) ──────────────────────

@pytest.mark.asyncio
async def test_adaptive_planner_replan_from_point():
    """Lines 94-148: replan creates recovery steps and re-numbers remaining steps."""
    from src.planning.adaptive_planner import AdaptivePlanner

    planner = AdaptivePlanner()
    original = {
        "plan_id": "orig-001",
        "steps": [
            {"step": 1, "action": "analyze", "description": "Analyze", "estimated_time": 5, "dependencies": []},
            {"step": 2, "action": "implement", "description": "Implement", "estimated_time": 30, "dependencies": [1]},
            {"step": 3, "action": "validate", "description": "Validate", "estimated_time": 10, "dependencies": [2]},
        ],
    }
    failed = original["steps"][1]  # step 2 fails
    reflection = {"reason": "timeout", "score": 0.3}

    new_plan = await planner.replan_from_point(original, failed, reflection)

    assert new_plan["replanned"] is True
    assert new_plan["parent_plan"] == "orig-001"
    assert new_plan["plan_id"] != "orig-001"
    assert "implement_timeout" in planner.failure_patterns
    # Recovery steps: diagnose, fix, retry → 3 recovery steps inserted
    actions = [s["action"] for s in new_plan["steps"]]
    assert "diagnose" in actions
    assert "fix" in actions
    assert new_plan["confidence"] < 0.8  # 0.9 multiplier applied


# ── adaptive_planner — analyze_failure branches (lines 150-165) ───────────────

def test_adaptive_planner_analyze_failure_timeout():
    """Lines 155-156: 'timeout' in message → reason='timeout'."""
    from src.planning.adaptive_planner import AdaptivePlanner

    planner = AdaptivePlanner()
    err = RuntimeError("Connection timeout exceeded")
    result = planner.analyze_failure(err, {"plan_id": "p1"})
    assert result["reason"] == "timeout"
    assert result["suggestion"] == "increase_timeout"
    assert result["plan_id"] == "p1"


def test_adaptive_planner_analyze_failure_memory():
    """Lines 157-158: 'memory' in message → reason='memory_limit'."""
    from src.planning.adaptive_planner import AdaptivePlanner

    planner = AdaptivePlanner()
    err = MemoryError("out of memory")
    result = planner.analyze_failure(err, {"plan_id": "p2"})
    assert result["reason"] == "memory_limit"
    assert result["suggestion"] == "optimise_memory"


def test_adaptive_planner_analyze_failure_unknown():
    """Lines 151-154: unknown error → reason='unknown', suggestion='investigate'."""
    from src.planning.adaptive_planner import AdaptivePlanner

    planner = AdaptivePlanner()
    err = ValueError("generic failure")
    result = planner.analyze_failure(err, {"plan_id": "p3"})
    assert result["reason"] == "unknown"
    assert result["suggestion"] == "investigate"
    assert result["error_type"] == "ValueError"


# ── continuous_evaluator — full evaluation path (lines 21-45) ─────────────────

@pytest.mark.asyncio
async def test_continuous_evaluator_evaluate_agent_performance():
    """Lines 21-45: evaluate_agent_performance calls sub-evaluators and records metrics."""
    from src.evaluation.continuous_evaluator import ContinuousEvaluator

    ev = ContinuousEvaluator()
    task_result = {
        "success": True,
        "confidence": 0.8,
        "technical_score": 0.9,
        "business_score": 0.6,
        "improvement": 0.15,
    }
    summary = await ev.evaluate_agent_performance("developer", task_result)

    assert summary["agent"] == "developer"
    assert summary["technical_score"] == 0.9
    assert summary["business_score"] == 0.6
    assert summary["improvement"] == 0.15
    # Lines 30-31: _record calls
    assert len(ev.metrics["task_success_rate"]) == 1
    assert len(ev.metrics["average_confidence"]) == 1


# ── consensus/weighted_voting — reach_consensus paths ─────────────────────────

def test_weighted_consensus_empty_proposals():
    """Lines 33-34: no proposals → decision=None, strength=0.0."""
    from src.consensus.weighted_voting import WeightedConsensusEngine

    engine = WeightedConsensusEngine()
    result = engine.reach_consensus({}, "architecture")
    assert result["decision"] is None
    assert result["consensus_strength"] == 0.0
    assert result["decision_maker"] is None


def test_weighted_consensus_with_proposals():
    """Lines 24-47: multiple proposals → winner + dissenting opinions."""
    from src.consensus.weighted_voting import WeightedConsensusEngine

    engine = WeightedConsensusEngine()
    proposals = {
        "architect": {"confidence": 0.9, "choice": "microservices"},
        "developer": {"confidence": 0.6, "choice": "monolith"},
        "auditor": {"confidence": 0.8, "choice": "microservices"},
    }
    result = engine.reach_consensus(proposals, "architecture")

    assert result["decision"] is not None
    assert 0.0 < result["consensus_strength"] <= 1.0
    assert result["decision_maker"] in {"architect", "developer", "auditor"}
    # At least 2 agents are not the winner → dissenting
    assert len(result["dissenting_opinions"]) >= 1


# ── architect_agent — execute() full path (lines 25-44) ──────────────────────

@pytest.mark.asyncio
async def test_architect_agent_execute():
    """Lines 25-44: execute() runs reason_with_cot, create_plan, create_adr."""
    from src.agents.architect_agent import ArchitectAgent

    agent = ArchitectAgent()
    result = await agent.execute({"description": "Design caching layer for API"})

    assert result["success"] is True
    assert "reasoning" in result
    assert "plan" in result
    assert "adr" in result
    assert result["confidence"] == 0.85
    # "cache" in recommendation → Caching Layer added (line 103-104)
    assert "Caching Layer" in result["plan"]["components"]
    # ADR string contains the title
    assert "ADR:" in result["adr"]


@pytest.mark.asyncio
async def test_architect_agent_execute_invalid():
    """Lines 22-23: empty task → ValueError."""
    from src.agents.architect_agent import ArchitectAgent

    agent = ArchitectAgent()
    with pytest.raises(ValueError, match="Invalid architectural task payload"):
        await agent.execute({})


# ── designer_agent — execute() branches (lines 21-24, 31->33) ────────────────

@pytest.mark.asyncio
async def test_designer_agent_execute_with_hero():
    """Lines 21-24: execute() with landing_page=True adds hero; dark theme."""
    from src.agents.designer_agent import DesignerAgent

    agent = DesignerAgent()
    result = await agent.execute({
        "description": "Landing page",
        "landing_page": True,
        "theme": "dark",
    })
    assert result["success"] is True
    assert "hero" in result["components"]                    # line 31->33
    assert result["colors"]["background"] == "#121212"       # dark theme
    assert result["theme"] == "dark"


@pytest.mark.asyncio
async def test_designer_agent_fallback_pattern():
    """Line 28: unknown pattern → fallback to 'material'."""
    from src.agents.designer_agent import DesignerAgent

    agent = DesignerAgent()
    result = await agent.execute({"description": "UI design", "pattern": "nonexistent"})
    assert result["pattern"] == "material"


@pytest.mark.asyncio
async def test_designer_agent_execute_invalid():
    """Lines 18-19: empty task → ValueError."""
    from src.agents.designer_agent import DesignerAgent

    agent = DesignerAgent()
    with pytest.raises(ValueError, match="Invalid design task payload"):
        await agent.execute({})


# ── backtest route — equity loop body (lines 120-123) ────────────────────────

def test_backtest_result_to_out_with_trades():
    """Lines 120-123: _result_to_out with non-empty trades builds equity curve."""
    from src.api.routes.backtest import _result_to_out
    from src.backtest.engine import BacktestResult, BacktestTrade

    trades = [
        BacktestTrade(candle_index=0, action="BUY", entry_price=50000.0, exit_price=51000.0,
                      position_size_pct=2.0, pnl_usdt=20.0, pnl_pct=0.02),
        BacktestTrade(candle_index=5, action="SELL", entry_price=51000.0, exit_price=50500.0,
                      position_size_pct=2.0, pnl_usdt=-10.0, pnl_pct=-0.01),
    ]
    result = BacktestResult(
        total_trades=2, win_rate=0.5, total_pnl_usdt=10.0, total_pnl_pct=0.001,
        max_drawdown_pct=0.02, sharpe_ratio=1.5, profit_factor=2.0,
        avg_win_pct=0.02, avg_loss_pct=-0.01, trades=trades,
    )
    out = _result_to_out(result, initial_capital=10000.0)
    assert len(out.equity) == 2                        # one EquityPoint per trade
    assert out.equity[0].equity == 10020.0             # 10000 + 20
    assert out.sharpe == 1.5
    assert out.profit_factor == 2.0


# ── backtest route — _run_job exception (lines 154-155) ──────────────────────

@pytest.mark.asyncio
async def test_backtest_run_job_exception(tmp_path, monkeypatch):
    """Lines 154-155: fetch_ohlcv raises → _mark_error called."""
    from src.api.routes.backtest import _run_job
    from src.api.schemas import BacktestConfigIn
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    job_id = "test-job-001"
    config = BacktestConfigIn()
    client = MagicMock()
    client.fetch_ohlcv = AsyncMock(side_effect=RuntimeError("fetch failed"))

    # _run_job catches the exception and calls _mark_error (no raise)
    await _run_job(job_id, config, client, initial_capital=10000.0)


# ── backtest route — walkforward endpoint (lines 242-262) ────────────────────

def test_backtest_walkforward_route(tmp_path, monkeypatch):
    """Lines 242-262: POST /walkforward runs WalkForwardValidator."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.api.deps import get_exchange_client
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    ts = 1_700_000_000_000
    # Need ≥ 300 candles for WalkForwardValidator(window_size=200, test_size=50, min_windows=2)
    ohlcv = [[ts + i * 3600_000, 50000.0 + i, 50100.0 + i, 49900.0 + i, 50000.0 + i, 100.0]
             for i in range(500)]
    mc = MagicMock()
    mc.fetch_ohlcv = AsyncMock(return_value=ohlcv)

    app = create_app()
    app.dependency_overrides[get_exchange_client] = lambda: mc
    client = TestClient(app)

    r = client.post("/v1/backtest/walkforward", json={})
    assert r.status_code == 200
    data = r.json()["data"]
    assert "valid" in data
    assert "windows" in data


# ── backtest — _build_histogram branches (lines 272, 276-282) ─────────────────

def test_backtest_histogram_empty():
    """Line 272: _build_histogram([]) → ([], [])."""
    from src.api.routes.backtest import _build_histogram

    counts, edges = _build_histogram([])
    assert counts == []
    assert edges == []


def test_backtest_histogram_varied():
    """Lines 276-282: varied values → histogram with counts and edges."""
    from src.api.routes.backtest import _build_histogram

    values = [1.0, 2.5, 3.0, 4.5, 5.0, 6.0, 7.5, 8.0, 9.0, 10.0]
    counts, edges = _build_histogram(values, bins=5)
    assert len(counts) == 5
    assert len(edges) == 5
    assert sum(counts) == len(values)


def test_backtest_histogram_all_equal():
    """Lines 274-275: lo==hi → first bin gets all, rest 0."""
    from src.api.routes.backtest import _build_histogram

    values = [5.0, 5.0, 5.0]
    counts, edges = _build_histogram(values, bins=4)
    assert counts[0] == 3
    assert sum(counts[1:]) == 0


# ── unified_orchestrator — low consensus rejected (lines 62-72) ───────────────

@pytest.mark.asyncio
async def test_unified_orchestrator_low_consensus_rejected():
    """Lines 62-72: consensus_strength < 0.7 → autonomy.executed=False → rejected."""
    from src.orchestration.unified_orchestrator import UnifiedOrchestrator

    orch = UnifiedOrchestrator.__new__(UnifiedOrchestrator)
    orch.memory = MagicMock()
    orch.memory.recall_similar = MagicMock(return_value=[])
    orch.memory.remember_decision = MagicMock()
    orch.planner = MagicMock()
    orch.planner.create_adaptive_plan = AsyncMock(return_value={"steps": [], "goal": "test"})
    orch.consensus = MagicMock()
    orch.consensus.reach_consensus = MagicMock(return_value={
        "consensus_strength": 0.3,  # < 0.7 → enter low-consensus block
        "decision": None,
    })
    orch.autonomy = MagicMock()
    orch.autonomy.execute_with_autonomy = AsyncMock(return_value={
        "executed": False,  # autonomy denies → plan rejected
    })

    with patch.object(orch, "_get_squad_proposals", AsyncMock(return_value={})):
        result = await orch.execute_complex_task({"description": "test", "task_id": "t-001"})

    assert result["success"] is False
    assert result["reason"] == "Plan rejected"


# ── unified_orchestrator — _get_squad_proposals (lines 103-133) ───────────────

@pytest.mark.asyncio
async def test_unified_orchestrator_get_squad_proposals():
    """Lines 103-133: _get_squad_proposals calls architect, developer, auditor."""
    from src.orchestration.unified_orchestrator import UnifiedOrchestrator

    orch = UnifiedOrchestrator.__new__(UnifiedOrchestrator)
    orch.agents = {
        "architect": MagicMock(execute=AsyncMock(return_value={"confidence": 0.9})),
        "developer": MagicMock(execute=AsyncMock(return_value={"confidence": 0.7})),
        "auditor": MagicMock(execute=AsyncMock(return_value={"confidence": 0.8})),
    }

    plan = {"goal": "test plan", "steps": []}
    proposals = await orch._get_squad_proposals(plan)

    assert "architect" in proposals
    assert "developer" in proposals
    assert "auditor" in proposals
    assert proposals["architect"]["confidence"] == 0.9
    orch.agents["architect"].execute.assert_awaited_once()


# ── unified_orchestrator — _update_learning (lines 184-189) ──────────────────

@pytest.mark.asyncio
async def test_unified_orchestrator_update_learning():
    """Lines 184-189: _update_learning iterates results, calls update_route_performance."""
    from src.orchestration.unified_orchestrator import UnifiedOrchestrator

    orch = UnifiedOrchestrator.__new__(UnifiedOrchestrator)
    orch.router = MagicMock()
    orch.router.update_route_performance = MagicMock()

    task = {"description": "test task"}
    results = [
        {"route": "fast", "success": True, "duration": 1.2},
        {"route": "default", "success": False, "duration": 0.5},
    ]
    await orch._update_learning(task, results)

    assert orch.router.update_route_performance.call_count == 2


# ── squad_orchestrator — _request_human_approval handler=None (lines 138-140) ─

@pytest.mark.asyncio
async def test_squad_orchestrator_approval_handler_none():
    """Lines 138-140: approval_handler=None → fail-closed return False."""
    from src.orchestration.squad_orchestrator import SquadOrchestrator

    orch = SquadOrchestrator.__new__(SquadOrchestrator)
    orch.approval_handler = None
    orch._last_order_ref = None

    result = await orch._request_human_approval({"action": "BUY"})
    assert result is False
    assert orch._last_order_ref is None


# ── squad_orchestrator — _log_fill with valid signal (lines 256-277) ──────────

def test_squad_orchestrator_log_fill_valid_signal():
    """Lines 256-277: _log_fill records fill and adds to _open_positions."""
    from src.orchestration.squad_orchestrator import SquadOrchestrator

    orch = SquadOrchestrator.__new__(SquadOrchestrator)
    orch.ledger = MagicMock()
    orch.ledger.log_fill = MagicMock()
    orch._open_positions = {}
    orch.initial_capital = 10_000.0

    signal = {
        "action": "buy",
        "entry_price": 50000.0,
        "position_size_pct": 2.0,
        "symbol": "BTC/USDT",
        "stop_loss": 49000.0,
        "take_profit": 52500.0,
    }
    execution = {"order_id": "ord-001"}
    orch._log_fill("BTC/USDT", signal, execution)

    orch.ledger.log_fill.assert_called_once()
    assert "ord-001" in orch._open_positions
    pos = orch._open_positions["ord-001"]
    assert pos["stop_loss"] == 49000.0
    assert pos["take_profit"] == 52500.0


def test_squad_orchestrator_log_fill_zero_price_skips():
    """Lines 254-255: entry_price=0 → early return, no fill recorded."""
    from src.orchestration.squad_orchestrator import SquadOrchestrator

    orch = SquadOrchestrator.__new__(SquadOrchestrator)
    orch.ledger = MagicMock()
    orch._open_positions = {}
    orch.initial_capital = 10_000.0

    orch._log_fill("BTC/USDT", {"entry_price": 0.0, "position_size_pct": 2.0}, {})
    orch.ledger.log_fill.assert_not_called()


# ── squad_orchestrator — _exit_price branches (lines 322-330) ─────────────────

def test_squad_orchestrator_exit_price_buy_stop_loss():
    """Lines 322-323: buy side, current_price <= stop_loss → return sl."""
    from src.orchestration.squad_orchestrator import SquadOrchestrator

    pos = {"side": "buy", "stop_loss": 49000.0, "take_profit": 52000.0}
    result = SquadOrchestrator._exit_price(pos, 48500.0)  # below SL
    assert result == 49000.0


def test_squad_orchestrator_exit_price_buy_take_profit():
    """Lines 324-325: buy side, current_price >= take_profit → return tp."""
    from src.orchestration.squad_orchestrator import SquadOrchestrator

    pos = {"side": "buy", "stop_loss": 49000.0, "take_profit": 52000.0}
    result = SquadOrchestrator._exit_price(pos, 53000.0)  # above TP
    assert result == 52000.0


def test_squad_orchestrator_exit_price_sell_stop_loss():
    """Lines 327-328: sell side, current_price >= stop_loss → return sl."""
    from src.orchestration.squad_orchestrator import SquadOrchestrator

    pos = {"side": "sell", "stop_loss": 52000.0, "take_profit": 48000.0}
    result = SquadOrchestrator._exit_price(pos, 53000.0)  # above SL for short
    assert result == 52000.0


def test_squad_orchestrator_exit_price_sell_take_profit():
    """Lines 329-330: sell side, current_price <= take_profit → return tp."""
    from src.orchestration.squad_orchestrator import SquadOrchestrator

    pos = {"side": "sell", "stop_loss": 52000.0, "take_profit": 48000.0}
    result = SquadOrchestrator._exit_price(pos, 47000.0)  # below TP for short
    assert result == 48000.0


def test_squad_orchestrator_exit_price_no_exit():
    """Line 331: price between SL and TP → return None."""
    from src.orchestration.squad_orchestrator import SquadOrchestrator

    pos = {"side": "buy", "stop_loss": 49000.0, "take_profit": 52000.0}
    result = SquadOrchestrator._exit_price(pos, 50500.0)  # between SL and TP
    assert result is None


# ── squad_orchestrator — _check_open_positions closes positions (lines 294-310) ─

def test_squad_orchestrator_check_open_positions_closes():
    """Lines 294-310: position SL hit → closed, ledger called, circuit breaker updated."""
    from src.orchestration.squad_orchestrator import SquadOrchestrator

    orch = SquadOrchestrator.__new__(SquadOrchestrator)
    orch.ledger = MagicMock()
    orch.ledger.log_position_closed = MagicMock()
    orch.circuit_breaker = MagicMock()
    orch.circuit_breaker.record_trade_result = MagicMock()
    orch._open_positions = {
        "ord-buy-001": {
            "symbol": "BTC/USDT",
            "side": "buy",
            "entry_price": 50000.0,
            "quantity": 0.1,
            "stop_loss": 49000.0,
            "take_profit": 53000.0,
            "opened_at": "2024-01-01T00:00:00",
        }
    }

    # current_price = 48500 (below stop_loss=49000) → position closed
    orch._check_open_positions(48500.0, "BTC/USDT")

    assert "ord-buy-001" not in orch._open_positions  # position was removed
    orch.ledger.log_position_closed.assert_called_once()
    orch.circuit_breaker.record_trade_result.assert_called_once()
    # PnL: buy direction, exit=49000 - entry=50000 = -1000 * 0.1 = -100 → negative pnl_pct
    pnl_pct = orch.circuit_breaker.record_trade_result.call_args[0][0]
    assert pnl_pct < 0


def test_squad_orchestrator_check_open_positions_sell_side_close():
    """Lines 305: sell side direction=-1.0 correctly computes PnL."""
    from src.orchestration.squad_orchestrator import SquadOrchestrator

    orch = SquadOrchestrator.__new__(SquadOrchestrator)
    orch.ledger = MagicMock()
    orch.circuit_breaker = MagicMock()
    orch._open_positions = {
        "ord-sell-001": {
            "symbol": "ETH/USDT",
            "side": "sell",
            "entry_price": 3000.0,
            "quantity": 1.0,
            "stop_loss": 3200.0,  # SL for short is above entry
            "take_profit": 2500.0,
            "opened_at": "2024-01-01T00:00:00",
        }
    }

    # current_price = 2400 < take_profit=2500 → TP hit for short
    orch._check_open_positions(2400.0, "ETH/USDT")

    assert "ord-sell-001" not in orch._open_positions
    # sell PnL: direction=-1 * (exit=2500 - entry=3000) * 1 = -1 * -500 = +500 > 0
    pnl_pct = orch.circuit_breaker.record_trade_result.call_args[0][0]
    assert pnl_pct > 0
