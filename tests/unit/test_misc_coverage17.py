"""Seventeenth batch — market flat candles, risk patch, unified orchestrator tasks,
adaptive planner confidence, config branches, progressive autonomy modifications,
squad orchestrator signal/fill/alert paths."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── market volume-profile — flat candles → out_bins = [] (line 322) ───────────

def test_market_volume_profile_flat_candles(tmp_path, monkeypatch):
    """Line 322: price_max == price_min → else branch → out_bins = []."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.api.deps import get_exchange_client
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    ts = 1_700_000_000_000
    # All candles have hi == lo == 50000 → price_max == price_min → else: out_bins=[]
    ohlcv = [[ts + i * 3600_000, 50000.0, 50000.0, 50000.0, 50000.0, 100.0] for i in range(200)]
    mc = MagicMock()
    mc.fetch_ohlcv = AsyncMock(return_value=ohlcv)

    app = create_app()
    app.dependency_overrides[get_exchange_client] = lambda: mc
    client = TestClient(app)

    r = client.get("/v1/market/BTC-USDT/volume-profile")
    assert r.status_code == 200
    assert r.json()["data"]["bins"] == []


# ── risk — patch_risk_config without max_position_size_pct (branch 267->269) ──

def test_risk_patch_no_max_position_size(tmp_path, monkeypatch):
    """Branch 267->269: max_position_size_pct not in updates → False → skip to 269."""
    import yaml
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.api.deps import get_exchange_client
    from src.core.db import init_db
    import src.api.routes.risk as risk_mod

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    yaml_file = tmp_path / "risk.yaml"
    yaml_file.write_text(
        "position_limits:\n  max_position_size_pct: 5.0\n"
        "stop_loss:\n  default_pct: 3.0\n"
    )
    monkeypatch.setattr(risk_mod, "_RISK_PARAMS_PATH", yaml_file)

    mc = MagicMock()
    mc.fetch_ohlcv = AsyncMock(return_value=[])

    app = create_app()
    app.dependency_overrides[get_exchange_client] = lambda: mc
    client = TestClient(app)

    # Only stop_loss_default_pct — max_position_size_pct NOT in updates → False branch at 267
    r = client.patch("/v1/risk/config", json={"stop_loss_default_pct": 4.0, "confirm": True})
    assert r.status_code == 200
    # stop_loss_default_pct was applied
    assert r.json()["data"]["stop_loss_default_pct"] == 4.0


# ── unified_orchestrator — extract_parallel_tasks coroutine bodies (177, 180) ─

@pytest.mark.asyncio
async def test_unified_orchestrator_parallel_task_bodies():
    """Lines 177, 180: call developer_task() and designer_task() to cover their bodies."""
    from src.orchestration.unified_orchestrator import UnifiedOrchestrator

    orch = UnifiedOrchestrator.__new__(UnifiedOrchestrator)
    dev_result = {"success": True, "type": "dev"}
    des_result = {"success": True, "type": "des"}
    orch.agents = {
        "developer": MagicMock(execute=AsyncMock(return_value=dev_result)),
        "designer": MagicMock(execute=AsyncMock(return_value=des_result)),
    }

    step = {"description": "Build something", "action": "implement"}
    tasks = orch._extract_parallel_tasks(step)
    assert len(tasks) == 2

    # Actually call the coroutines so lines 177 and 180 execute
    result1 = await tasks[0]()  # developer_task body (line 177)
    result2 = await tasks[1]()  # designer_task body (line 180)

    assert result1 == dev_result
    assert result2 == des_result
    orch.agents["developer"].execute.assert_awaited_once()
    orch.agents["designer"].execute.assert_awaited_once()


# ── adaptive_planner — _calculate_plan_confidence with >5 steps (line 90) ─────

def test_adaptive_planner_confidence_six_steps():
    """Line 90: len(steps) > 5 → confidence -= 0.1."""
    from src.planning.adaptive_planner import AdaptivePlanner

    planner = AdaptivePlanner()
    # 6 steps → len > 5 → line 90 executes
    plan = {"steps": [{} for _ in range(6)], "estimated_duration": 60}
    confidence = planner._calculate_plan_confidence(plan)
    # 0.8 - 0.1 = 0.7 (estimated_duration=60 ≤ 120, so no second deduction)
    assert confidence == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_adaptive_planner_replan_yields_more_than_5_steps():
    """Line 90 via replan: recovery adds 3 steps so total may exceed 5."""
    from src.planning.adaptive_planner import AdaptivePlanner

    planner = AdaptivePlanner()
    # Original plan: 4 steps. After replan (completed=1, recovery=3, remaining=2) = 6 steps
    original_plan = {
        "plan_id": "orig",
        "steps": [
            {"step": 1, "action": "analyze", "description": "A", "estimated_time": 5, "dependencies": []},
            {"step": 2, "action": "design",  "description": "D", "estimated_time": 15, "dependencies": [1]},
            {"step": 3, "action": "implement","description": "I","estimated_time": 30, "dependencies": [2]},
            {"step": 4, "action": "validate", "description": "V","estimated_time": 10, "dependencies": [3]},
        ],
        "estimated_duration": 60,
    }
    failed_step = original_plan["steps"][1]  # step 2 fails
    reflection = {"reason": "low_quality", "score": 0.3}

    new_plan = await planner.replan_from_point(original_plan, failed_step, reflection)
    # completed(1) + recovery(3) + remaining(2) = 6 steps → confidence -= 0.1
    assert len(new_plan["steps"]) > 5


# ── config — patch_config without initial_capital (branch 75->77) ─────────────

def test_config_patch_without_initial_capital(tmp_path, monkeypatch):
    """Branch 75->77: initial_capital NOT in updates → False branch at line 75."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.api.deps import get_exchange_client
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    mc = MagicMock()
    mc.fetch_ohlcv = AsyncMock(return_value=[])

    app = create_app()
    app.dependency_overrides[get_exchange_client] = lambda: mc
    client = TestClient(app)

    # Only orchestrator_interval_seconds → initial_capital NOT in updates → line 75 False
    r = client.patch("/v1/config", json={"orchestrator_interval_seconds": 30})
    assert r.status_code == 200
    assert r.json()["data"]["orchestrator_interval_seconds"] == 30


# ── config — patch_agent_config agent_id not in AGENT_PARAMS (branch 95->97) ──

def test_config_patch_agent_not_in_params(tmp_path, monkeypatch):
    """Branch 95->97: agent_id in AGENT_REGISTRY but NOT in AGENT_PARAMS → skip line 96."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.api.deps import get_exchange_client
    from src.core.db import init_db
    from src.agents.registry import AgentInfo

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    mc = MagicMock()
    mc.fetch_ohlcv = AsyncMock(return_value=[])

    app = create_app()
    app.dependency_overrides[get_exchange_client] = lambda: mc
    client = TestClient(app)

    new_agent = AgentInfo("test_agent_x", "trading", True, "test agent")

    # test_agent_x in AGENT_REGISTRY but not in AGENT_PARAMS → False branch of line 95
    with patch.dict("src.agents.registry.AGENT_REGISTRY", {"test_agent_x": new_agent}):
        r = client.patch("/v1/agents/test_agent_x/config", json={"some_param": 1})
        assert r.status_code == 200
        assert r.json()["data"]["id"] == "test_agent_x"


# ── config — patch_agent_config agent_id not found (line 94: 404) ─────────────

def test_config_patch_agent_not_found_404(tmp_path, monkeypatch):
    """Line 94: agent_id not in AGENT_REGISTRY → 404."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.api.deps import get_exchange_client
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    mc = MagicMock()
    mc.fetch_ohlcv = AsyncMock(return_value=[])

    app = create_app()
    app.dependency_overrides[get_exchange_client] = lambda: mc
    client = TestClient(app)

    r = client.patch("/v1/agents/nonexistent_agent_xyz/config", json={"some_param": 1})
    assert r.status_code == 404


# ── progressive_autonomy — modifications branch (line 47->49) ─────────────────

@pytest.mark.asyncio
async def test_progressive_autonomy_with_modifications():
    """Line 47->49: approval returns modifications → action is updated before execution."""
    from src.hitl.progressive_autonomy import ProgressiveAutonomyManager

    manager = ProgressiveAutonomyManager()
    # Agent trust score defaults to 0.5 → level 1 → needs_approval = True
    modifications = {"extra_field": "extra_value", "critical": False}
    approval_response = {
        "approved": True,
        "modifications": modifications,
        "feedback": None,
    }
    manager.approval_handler = AsyncMock(return_value=approval_response)

    result = await manager.execute_with_autonomy("agent1", {"action": "buy", "critical": False})
    # Executed successfully with modifications applied
    assert result["executed"] is True
    # The action passed to _execute_action should have been merged with modifications
    manager.approval_handler.assert_awaited_once()


# ── squad_orchestrator — signal with no entry_price (branch 171->177) ─────────

@pytest.mark.asyncio
async def test_squad_orchestrator_zero_entry_price_skips_position_check():
    """Branch 171->177: entry_price=0 → current_price=0 → skip _check_open_positions."""
    from src.orchestration.squad_orchestrator import SquadOrchestrator

    orch = SquadOrchestrator.__new__(SquadOrchestrator)
    orch.strategy_agent = MagicMock()
    orch.strategy_agent.execute = AsyncMock(return_value={
        "success": True,
        # No entry_price → entry_price=0 → current_price=0 → skip line 172-175
        "signal": {"action": "HOLD"},
        "confidence": 0.4,  # < 0.6 → early return after log_signal
    })
    orch.ledger = MagicMock()
    orch.ledger.log_signal = MagicMock()
    orch.circuit_breaker = MagicMock()
    orch.circuit_breaker.is_open = False
    orch.alert_store = None
    orch.alert_bus = None
    orch.approval_handler = None
    orch.fill_callback = None
    orch._last_order_ref = None
    orch.initial_capital = 10_000.0
    orch._open_positions = {}

    # _check_open_positions should NOT be called (entry_price absent → current_price=0)
    check_called = []
    def _check_positions(price, symbol):
        check_called.append(True)
    orch._check_open_positions = _check_positions

    result = await orch.analyze_and_trade(symbol="BTC/USDT")
    assert result["success"] is False
    assert result["reason"] == "Low confidence signal"
    # _check_open_positions was NOT called (branch 171->177 taken)
    assert check_called == []


# ── squad_orchestrator — execution success, fill_callback=None (branch 226->236)

@pytest.mark.asyncio
async def test_squad_orchestrator_execution_success_no_fill_callback():
    """Branch 226->236: execution succeeds but fill_callback=None → skip callback."""
    from src.orchestration.squad_orchestrator import SquadOrchestrator

    orch = SquadOrchestrator.__new__(SquadOrchestrator)
    orch.strategy_agent = MagicMock()
    orch.strategy_agent.execute = AsyncMock(return_value={
        "success": True,
        "signal": {
            "action": "BUY",
            "entry_price": 50_000.0,
            "position_size_pct": 1.0,
            "stop_loss": 49_000.0,
            "take_profit": 52_500.0,
        },
        "confidence": 0.8,
    })
    orch.risk_agent = MagicMock()
    orch.risk_agent.execute = AsyncMock(return_value={
        "approved": True,
        "signal": {
            "action": "BUY",
            "entry_price": 50_000.0,
            "stop_loss": 49_000.0,
            "take_profit": 52_500.0,
        },
        "validation": {"issues": []},
        "warnings": [],
    })
    orch.execution_agent = MagicMock()
    orch.execution_agent.execute = AsyncMock(return_value={
        "success": True,  # execution succeeds
        "order_id": "ord-test-001",
    })
    orch.ledger = MagicMock()
    orch.ledger.log_signal = MagicMock()
    orch.ledger.log_validation = MagicMock()
    orch.ledger.log_execution = MagicMock()
    orch.ledger.log_hitl_approval = MagicMock()
    orch.ledger.log_fill = MagicMock()
    orch.circuit_breaker = MagicMock()
    orch.circuit_breaker.is_open = False
    # fill_callback=None → line 226 condition False → branch 226->236 taken
    orch.fill_callback = None
    orch._last_order_ref = None
    orch.initial_capital = 10_000.0
    orch.alert_store = None
    orch.alert_bus = None
    orch._open_positions = {}
    orch._check_open_positions = MagicMock()
    # approval_handler returns True (bool) → _last_order_ref stays None
    orch.approval_handler = AsyncMock(return_value=True)

    result = await orch.analyze_and_trade(symbol="BTC/USDT")
    assert result["success"] is True
    assert result["order_id"] == "ord-test-001"
    # _last_order_ref reset to None at line 236
    assert orch._last_order_ref is None


# ── squad_orchestrator — _emit_alert with alert_bus only (branch 345->347) ─────

@pytest.mark.asyncio
async def test_squad_orchestrator_emit_alert_bus_only():
    """Branch 345->347: alert_store=None, alert_bus not None → skip append, do publish."""
    from src.orchestration.squad_orchestrator import SquadOrchestrator
    from src.core.alerts import AlertBus

    alert_bus = AlertBus()
    published = []
    alert_bus.publish = AsyncMock(side_effect=lambda a: published.append(a))

    orch = SquadOrchestrator.__new__(SquadOrchestrator)
    orch.strategy_agent = MagicMock()
    orch.strategy_agent.execute = AsyncMock(return_value={
        "success": True,
        "signal": {"action": "BUY", "entry_price": 50_000.0},
        "confidence": 0.8,
    })
    orch.risk_agent = MagicMock()
    orch.risk_agent.execute = AsyncMock(return_value={
        "approved": False,  # risk rejects → _emit_alert is called
        "signal": {"action": "BUY", "entry_price": 50_000.0},
        "validation": {"issues": ["stop loss too wide"]},
        "warnings": ["Stop loss too wide"],
    })
    orch.ledger = MagicMock()
    orch.ledger.log_signal = MagicMock()
    orch.ledger.log_validation = MagicMock()
    orch.circuit_breaker = MagicMock()
    orch.circuit_breaker.is_open = False
    orch.approval_handler = None
    orch.fill_callback = None
    orch._last_order_ref = None
    orch.initial_capital = 10_000.0
    # alert_store=None, alert_bus=alert_bus → branch 345->347 taken
    orch.alert_store = None
    orch.alert_bus = alert_bus
    orch._open_positions = {}
    orch._check_open_positions = MagicMock()

    result = await orch.analyze_and_trade(symbol="BTC/USDT")
    assert result["success"] is False
    assert result["reason"] == "Risk validation failed"
    # alert_bus.publish was called (line 348), but alert_store.append was NOT (line 345->347)
    assert len(published) == 1
