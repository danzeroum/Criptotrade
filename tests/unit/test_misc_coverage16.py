"""Sixteenth batch — market signals, risk config, orders conflict, orchestrator parallel."""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ─── helper: minimal FastAPI test client ─────────────────────────────────────

def _make_client(tmp_path, monkeypatch, mc=None):
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.api.deps import get_exchange_client
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    if mc is None:
        mc = MagicMock()

    app = create_app()
    app.dependency_overrides[get_exchange_client] = lambda: mc
    return TestClient(app), app, mc


# ── market — ValueError from TechnicalAnalyzer (lines 161-162) ────────────────

def test_market_indicators_value_error(tmp_path, monkeypatch):
    """Lines 161-162: < 50 candles → TechnicalAnalyzer raises ValueError → 422."""
    ts = 1_700_000_000_000
    ohlcv_short = [[ts + i * 3600_000, 50000.0, 50100.0, 49900.0, 50000.0, 100.0]
                   for i in range(10)]
    mc = MagicMock()
    mc.fetch_ohlcv = AsyncMock(return_value=ohlcv_short)
    client, _, _ = _make_client(tmp_path, monkeypatch, mc)

    r = client.get("/v1/market/BTC-USDT/indicators")
    assert r.status_code == 422


def test_market_regime_value_error(tmp_path, monkeypatch):
    """Lines 215-216: < 50 candles → ValueError → 422 in regime endpoint."""
    ts = 1_700_000_000_000
    mc = MagicMock()
    mc.fetch_ohlcv = AsyncMock(return_value=[
        [ts + i * 3600_000, 50000.0, 50100.0, 49900.0, 50000.0, 100.0] for i in range(5)
    ])
    client, _, _ = _make_client(tmp_path, monkeypatch, mc)

    r = client.get("/v1/market/BTC-USDT/regime")
    assert r.status_code == 422


def test_market_signal_value_error(tmp_path, monkeypatch):
    """Lines 382-383: < 50 candles → ValueError → 422 in signal endpoint."""
    ts = 1_700_000_000_000
    mc = MagicMock()
    mc.fetch_ohlcv = AsyncMock(return_value=[
        [ts + i * 3600_000, 50000.0, 50100.0, 49900.0, 50000.0, 100.0] for i in range(3)
    ])
    client, _, _ = _make_client(tmp_path, monkeypatch, mc)

    r = client.get("/v1/market/BTC-USDT/signal")
    assert r.status_code == 422


# ── market — signal RSI oversold / MACD bearish / chaotic regime ──────────────

def _signal_mock_client(rsi_val, macd_hist_val, macd_line_val, macd_signal_val, regime_val):
    """Build a mock exchange client + patched analyzer for signal tests."""
    import pandas as pd
    ts = 1_700_000_000_000
    ohlcv = [[ts + i * 3600_000, 50000.0, 50100.0, 49900.0, 50000.0, 100.0] for i in range(150)]
    mc = MagicMock()
    mc.fetch_ohlcv = AsyncMock(return_value=ohlcv)
    return mc, rsi_val, macd_hist_val, macd_line_val, macd_signal_val, regime_val


def test_market_signal_rsi_oversold_buy(tmp_path, monkeypatch):
    """Lines 401-403: RSI < 30 → buy_score += 0.4 → action='buy'."""
    mc = MagicMock()
    mc.fetch_ohlcv = AsyncMock(return_value=[
        [1_700_000_000_000 + i * 3600_000, 50000.0, 50100.0, 49900.0, 50000.0, 100.0]
        for i in range(150)
    ])
    client, app, _ = _make_client(tmp_path, monkeypatch, mc)

    mock_ind = MagicMock()
    mock_ind.rsi = 25.0            # < 30 → buy branch (lines 401-403)
    mock_ind.macd_hist = 0.5       # > 0 → buy MACD branch
    mock_ind.macd_line = 1.0
    mock_ind.macd_signal = 0.5
    mock_ind.ema_fast = 50200.0    # > ema_slow → strong_uptrend
    mock_ind.ema_slow = 50000.0
    mock_ind.atr = 100.0
    mock_ind.current_price = 50000.0
    mock_ind.stochastic_k = None
    mock_ind.bb_upper = None
    mock_ind.sma_20 = None
    mock_ind.sma_50 = None
    mock_ind.sma_200 = None
    mock_ind.volume_ratio = None
    mock_ind.obv = None
    mock_ind.bb_percent = None
    mock_ind.macd_signal = 0.5

    mock_analyzer = MagicMock()
    mock_analyzer.get_latest.return_value = mock_ind

    with patch("src.analysis.indicators.TechnicalAnalyzer", return_value=mock_analyzer):
        r = client.get("/v1/market/BTC-USDT/signal")

    assert r.status_code == 200
    data = r.json()["data"]
    assert data["action"] == "buy"


def test_market_signal_rsi_overbought_sell(tmp_path, monkeypatch):
    """Lines 404-406: RSI > 70 → sell_score += 0.4 → action='sell'."""
    mc = MagicMock()
    mc.fetch_ohlcv = AsyncMock(return_value=[
        [1_700_000_000_000 + i * 3600_000, 50000.0, 50100.0, 49900.0, 50000.0, 100.0]
        for i in range(150)
    ])
    client, app, _ = _make_client(tmp_path, monkeypatch, mc)

    mock_ind = MagicMock()
    mock_ind.rsi = 78.0            # > 70 → sell branch (lines 404-406)
    mock_ind.macd_hist = -0.5      # < 0 → sell MACD branch (lines 411-413)
    mock_ind.macd_line = -1.0
    mock_ind.macd_signal = -0.5
    mock_ind.ema_fast = 49800.0    # < ema_slow → downtrend
    mock_ind.ema_slow = 50000.0
    mock_ind.atr = 100.0
    mock_ind.current_price = 50000.0
    mock_ind.stochastic_k = None
    mock_ind.bb_upper = None
    mock_ind.sma_20 = None
    mock_ind.sma_50 = None
    mock_ind.sma_200 = None
    mock_ind.volume_ratio = None
    mock_ind.obv = None
    mock_ind.bb_percent = None

    mock_analyzer = MagicMock()
    mock_analyzer.get_latest.return_value = mock_ind

    with patch("src.analysis.indicators.TechnicalAnalyzer", return_value=mock_analyzer):
        r = client.get("/v1/market/BTC-USDT/signal")

    assert r.status_code == 200
    data = r.json()["data"]
    assert data["action"] == "sell"


def test_market_signal_chaotic_regime(tmp_path, monkeypatch):
    """Lines 419-421: chaotic regime → buy_score=sell_score=0 → action='hold'."""
    mc = MagicMock()
    mc.fetch_ohlcv = AsyncMock(return_value=[
        [1_700_000_000_000 + i * 3600_000, 50000.0, 50100.0, 49900.0, 50000.0, 100.0]
        for i in range(150)
    ])
    client, app, _ = _make_client(tmp_path, monkeypatch, mc)

    mock_ind = MagicMock()
    mock_ind.rsi = 50.0
    mock_ind.macd_hist = 0.0
    mock_ind.macd_line = 0.0
    mock_ind.macd_signal = 0.0
    mock_ind.ema_fast = 49000.0
    mock_ind.ema_slow = 50000.0
    mock_ind.atr = 3000.0          # ATR/price = 6% > 5% → chaotic
    mock_ind.current_price = 50000.0
    mock_ind.stochastic_k = None
    mock_ind.bb_upper = None
    mock_ind.sma_20 = None
    mock_ind.sma_50 = None
    mock_ind.sma_200 = None
    mock_ind.volume_ratio = None
    mock_ind.obv = None
    mock_ind.bb_percent = None

    mock_analyzer = MagicMock()
    mock_analyzer.get_latest.return_value = mock_ind

    with patch("src.analysis.indicators.TechnicalAnalyzer", return_value=mock_analyzer):
        r = client.get("/v1/market/BTC-USDT/signal")

    assert r.status_code == 200
    data = r.json()["data"]
    assert data["action"] == "hold"


# ── regime_detector — strong_downtrend branch (line 55 else) ──────────────────

def test_regime_detector_strong_downtrend():
    """Line 55 else: ema_fast < ema_slow, mild spread → 'strong_downtrend'."""
    from src.analysis.regime_detector import detect_regime

    result = detect_regime(
        ema_fast=49000.0,
        ema_slow=50000.0,
        atr=200.0,                 # volatility_pct = 200/50000 = 0.004 (not chaotic, not sideways)
        current_price=50000.0,
    )
    # ema_spread = |49000-50000|/50000 = 0.02 (not > 0.02, not < 0.01)
    # volatility_pct = 0.004 (not > 0.05, not < 0.02 for sideways check together)
    # Falls through to line 55: ema_fast(49000) < ema_slow(50000) → "strong_downtrend"
    assert result == "strong_downtrend"


# ── risk — circuit breaker disabled branch (lines 35-36, 143-144) ─────────────

def test_risk_circuit_breaker_disabled(tmp_path, monkeypatch):
    """Lines 35-36, 143-144: yaml with enabled=false → status='disabled'."""
    import src.api.routes.risk as risk_mod
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    yaml_file = tmp_path / "risk.yaml"
    yaml_file.write_text("loss_limits:\n  circuit_breaker:\n    enabled: false\n")
    monkeypatch.setattr(risk_mod, "_RISK_PARAMS_PATH", yaml_file)

    app = create_app()
    client = TestClient(app)

    r = client.get("/v1/risk/circuit-breaker")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "disabled"


# ── risk — patch_risk_config saves yaml (lines 41, 267-269) ───────────────────

def test_risk_patch_config_saves_yaml(tmp_path, monkeypatch):
    """Lines 41, 267-269: patch /risk/config with confirm=true updates and saves yaml."""
    import src.api.routes.risk as risk_mod
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    yaml_file = tmp_path / "risk.yaml"
    yaml_file.write_text("{}")
    monkeypatch.setattr(risk_mod, "_RISK_PARAMS_PATH", yaml_file)

    app = create_app()
    client = TestClient(app)

    r = client.patch(
        "/v1/risk/config",
        json={"confirm": True, "max_position_size_pct": 5.0},
    )
    assert r.status_code == 200
    # Verify file was written (line 41 covered)
    import yaml
    saved = yaml.safe_load(yaml_file.read_text())
    assert saved["position_limits"]["max_position_size_pct"] == 5.0


# ── risk — Kelly all-wins → risk_of_ruin=0 (line 201) ────────────────────────

def test_risk_kelly_all_wins_risk_of_ruin_zero(tmp_path, monkeypatch):
    """Line 201: win_rate=1.0 → win_rate < 1 is False → risk_of_ruin=0.0."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.api.deps import get_ledger, get_metrics_calculator
    from src.core.ledger import TradingLedger
    from src.core.metrics import PortfolioMetricsCalculator
    from src.core.db import init_db
    import datetime

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    # Create ledger with 12 all-winning position_closed entries (buy, exit > entry)
    ledger = TradingLedger(tmp_path / "r.jsonl")
    for i in range(12):
        ledger.log_position_closed(
            order_id=f"ord-{i}", symbol="BTC/USDT", side="buy",
            entry_price=50000.0, exit_price=51000.0 + i * 10,
            quantity=0.001,
        )
    calc = PortfolioMetricsCalculator(ledger, initial_capital=10_000.0)

    app = create_app()
    app.dependency_overrides[get_ledger] = lambda: ledger
    app.dependency_overrides[get_metrics_calculator] = lambda: calc
    client = TestClient(app)

    r = client.get("/v1/risk/kelly")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["data_quality"] == "ok"
    assert data["risk_of_ruin"] == 0.0  # win_rate=1.0 → line 201


# ── orders — 409 conflict error (lines 114-115) ───────────────────────────────

def test_orders_patch_conflict_409(tmp_path, monkeypatch):
    """Lines 114-115: order already resolved → OrderConflictError → 409."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.api.deps import get_order_store
    from src.core.db import init_db
    from src.hitl.orders import OrderConflictError, OrderStatus

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    # Mock store: get returns something (not 404), resolve raises conflict
    mock_store = MagicMock()
    mock_store.get.return_value = MagicMock()  # non-None → passes 404 check
    filled_order = MagicMock()
    filled_order.id = "ord-abc"
    filled_order.status = MagicMock()
    filled_order.status.value = "filled"
    mock_store.resolve.side_effect = OrderConflictError(filled_order)

    app = create_app()
    app.dependency_overrides[get_order_store] = lambda: mock_store
    client = TestClient(app)

    r = client.patch(
        "/v1/orders/ord-abc/status",
        json={"decision": "approve", "operator": "tester"},
    )
    assert r.status_code == 409


# ── hitl/orders — list with offset (lines 274-275) ───────────────────────────

def test_hitl_orders_list_with_offset(tmp_path, monkeypatch):
    """Lines 274-275: list_orders(offset=5) → OFFSET clause appended."""
    from src.hitl.orders import Order, OrderStore
    from src.core.ledger import TradingLedger
    from src.safety.guardrails import GuardrailSystem
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    ledger = TradingLedger(tmp_path / "t.jsonl")
    store = OrderStore(ledger, threshold_provider=lambda: 0.0,
                       guardrails=GuardrailSystem(),
                       db_path=str(tmp_path / "orders.db"))

    # Submit 3 orders with valid stop_loss/take_profit (passes guardrails)
    for i in range(3):
        store.submit(Order(
            pair="BTC/USDT", side="buy", quantity=0.001, price=50_000.0,
            strategy="test", agent_id="strategy", confidence=0.9,
            reason=f"test {i}", critical=False, position_size_pct=1.0,
            stop_loss=49_000.0, take_profit=52_500.0,
        ))

    # list with offset=2 → should return 1 order (3 total - 2 offset = 1)
    result = store.list(limit=10, offset=2)
    assert len(result) == 1  # offset=2 skips first 2


# ── hitl/orders — count with status filter (lines 290-291) ───────────────────

def test_hitl_orders_count_with_status(tmp_path, monkeypatch):
    """Lines 290-291: count(status=pending) → status clause in SQL."""
    from src.hitl.orders import Order, OrderStatus, OrderStore
    from src.core.ledger import TradingLedger
    from src.safety.guardrails import GuardrailSystem
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    ledger = TradingLedger(tmp_path / "t.jsonl")
    store = OrderStore(ledger, threshold_provider=lambda: 0.0,
                       guardrails=GuardrailSystem(),
                       db_path=str(tmp_path / "orders.db"))

    store.submit(Order(
        pair="BTC/USDT", side="buy", quantity=0.001, price=50_000.0,
        strategy="test", agent_id="strategy", confidence=0.9,
        reason="test", critical=False, position_size_pct=1.0,
        stop_loss=49_000.0, take_profit=52_500.0,  # passes guardrails (RR=2.5)
    ))

    count = store.count(status=OrderStatus.pending)
    assert count == 1  # threshold=0.0 → not auto-filled → stays pending
    count_all = store.count()
    assert count_all >= 1


# ── hitl/orders — wait_for_decision with nonexistent order (line 324) ────────

@pytest.mark.asyncio
async def test_hitl_orders_wait_for_nonexistent(tmp_path, monkeypatch):
    """Line 324: row is None → return False immediately (non-existent order)."""
    from src.hitl.orders import OrderStore
    from src.core.ledger import TradingLedger
    from src.safety.guardrails import GuardrailSystem
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    ledger = TradingLedger(tmp_path / "t.jsonl")
    store = OrderStore(ledger, threshold_provider=lambda: 0.0,
                       guardrails=GuardrailSystem(),
                       db_path=str(tmp_path / "orders.db"),
                       poll_interval=0.01)

    result = await asyncio.wait_for(
        store.wait_for_decision("nonexistent-order-id", timeout=5.0),
        timeout=10.0,
    )
    assert result is False  # line 324: row is None → return False


# ── developer_agent — execute() and react_loop (lines 29-38, 57) ──────────────

@pytest.mark.asyncio
async def test_developer_agent_execute():
    """Lines 29-38: execute() → react_loop runs max_iterations → incomplete."""
    from src.agents.developer_agent import DeveloperAgent

    agent = DeveloperAgent()
    result = await agent.execute({"description": "build REST API"})

    assert result["success"] is True
    # react_loop runs until max_iterations (5) without completing → line 57
    # OR completes if observation matches "complete/finished/generated"
    assert result.get("status") in ("completed", "incomplete")


@pytest.mark.asyncio
async def test_developer_agent_execute_invalid():
    """Lines 25-27: empty task → ValueError."""
    from src.agents.developer_agent import DeveloperAgent

    agent = DeveloperAgent()
    with pytest.raises(ValueError, match="Invalid development task payload"):
        await agent.execute({})


# ── unified_orchestrator — parallel execution (lines 140-145, 174-182) ────────

@pytest.mark.asyncio
async def test_unified_orchestrator_parallel_execution():
    """Lines 140-145, 174-182: step with no deps + action='analyze' → parallel."""
    from src.orchestration.unified_orchestrator import UnifiedOrchestrator

    orch = UnifiedOrchestrator.__new__(UnifiedOrchestrator)
    orch.agents = {
        "architect": MagicMock(execute=AsyncMock(return_value={"success": True, "duration": 1.0})),
        "developer": MagicMock(execute=AsyncMock(return_value={"success": True, "duration": 0.5})),
        "designer": MagicMock(execute=AsyncMock(return_value={"success": True, "duration": 0.5})),
    }
    orch.parallel = MagicMock()
    orch.parallel.execute_parallel_with_limits = AsyncMock(return_value=[
        {"success": True, "duration": 1.0},
    ])
    orch.evaluator = MagicMock()
    orch.evaluator.evaluate_agent_performance = AsyncMock(return_value={"technical_score": 0.8})
    orch.planner = MagicMock()
    orch.planner.replan_from_point = AsyncMock(return_value={
        "steps": []  # empty replan so loop terminates
    })

    # Step with no dependencies and non-validate/deploy action → _can_parallelize=True
    plan = {
        "steps": [
            {"step": 1, "action": "analyze", "description": "Analyze req", "dependencies": []},
        ]
    }
    results = await orch._execute_plan_steps(plan, {"description": "test"})

    # Lines 140-145: parallel path taken
    orch.parallel.execute_parallel_with_limits.assert_awaited_once()
    # Lines 174-182: _extract_parallel_tasks was called (returns [developer_task, designer_task])
    assert len(results) == 1


# ── unified_orchestrator — autonomy approved proceeds (line 66->74) ────────────

@pytest.mark.asyncio
async def test_unified_orchestrator_low_consensus_autonomy_approved():
    """Line 66->74: consensus < 0.7 but autonomy.executed=True → proceed."""
    from src.orchestration.unified_orchestrator import UnifiedOrchestrator

    orch = UnifiedOrchestrator.__new__(UnifiedOrchestrator)
    orch.memory = MagicMock()
    orch.memory.recall_similar = MagicMock(return_value=[])
    orch.memory.remember_decision = MagicMock()
    orch.planner = MagicMock()
    orch.planner.create_adaptive_plan = AsyncMock(return_value={"steps": [], "goal": "test"})
    orch.consensus = MagicMock()
    orch.consensus.reach_consensus = MagicMock(return_value={
        "consensus_strength": 0.3,  # < 0.7
    })
    orch.autonomy = MagicMock()
    orch.autonomy.execute_with_autonomy = AsyncMock(return_value={
        "executed": True,  # approved → 66->74 (skip rejection block)
    })
    orch.agents = {
        "auditor": MagicMock(
            validate_results=AsyncMock(return_value={"approved": True, "confidence": 0.9})
        )
    }
    orch.router = MagicMock()
    orch.router.update_route_performance = MagicMock()

    with patch.object(orch, "_get_squad_proposals", AsyncMock(return_value={})), \
         patch.object(orch, "_execute_plan_steps", AsyncMock(return_value=[])):
        result = await orch.execute_complex_task({"description": "test", "task_id": "t-100"})

    # Plan was NOT rejected (executed=True bypassed the rejection block)
    assert result.get("reason") != "Plan rejected"
    assert "success" in result


# ── api/schemas — operator_note required on reject (line 131) ─────────────────

def test_schemas_operator_note_required_on_reject():
    """Line 131: decision='reject' without operator_note → ValueError."""
    import pydantic
    from src.api.schemas import OrderDecisionPatch

    with pytest.raises((pydantic.ValidationError, ValueError)):
        OrderDecisionPatch(decision="reject", operator="tester")
        # operator_note missing → validator raises ValueError (line 131)
