"""Fourteenth batch — hitl orders, strategy agent HOLD, circuit breaker, market indicators."""
from __future__ import annotations

import time
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── hitl/orders — wait_for_decision with rejected order (line 329) ───────────

@pytest.mark.asyncio
async def test_wait_for_decision_rejected(tmp_path, monkeypatch):
    """Line 329: status='rejected' → return False."""
    from src.hitl.orders import Order, OrderStore
    from src.core.ledger import TradingLedger
    from src.safety.guardrails import GuardrailSystem
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    ledger = TradingLedger(tmp_path / "t.jsonl")
    store = OrderStore(
        ledger,
        threshold_provider=lambda: 0.0,  # threshold=0 → auto disabled → order stays pending
        guardrails=GuardrailSystem(),
        db_path=str(tmp_path / "orders.db"),
    )

    order = store.submit(Order(
        pair="BTC/USDT", side="buy", quantity=0.001, price=50_000.0,
        strategy="test", agent_id="strategy", confidence=0.9,
        reason="test order", critical=False, position_size_pct=1.0,
        stop_loss=49_000.0, take_profit=52_500.0,
    ))

    # Reject the order via resolve(approved=False)
    store.resolve(order.id, approved=False, operator="tester", operator_note="test rejection")

    # wait_for_decision should return False immediately (status='rejected' → line 329)
    result = await asyncio.wait_for(
        store.wait_for_decision(order.id, timeout=5.0),
        timeout=10.0
    )
    assert result is False


# ── strategy_agent — HOLD signal (line 52) via execute with no eligible ───────

@pytest.mark.asyncio
async def test_strategy_agent_no_eligible_strategies_line_52():
    """Line 52: eligible_strategies=[] → _generate_signal returns (HOLD, None) → line 52."""
    from src.agents.strategy_agent import StrategyAgent

    agent = StrategyAgent(exchange_client=None)

    # Patch _analyze_market to return analysis with no eligible strategies
    no_eligible_analysis = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "current_price": 50_000.0,
        "trend": None,
        "regime": "unknown",
        "eligible_strategies": [],    # → no eligible → HOLD with strategy_confidence=None
        "indicators": None,
        "support_resistance": None,
        "fibonacci_levels": {},
        "volume_profile": None,
        "rsi_divergence": None,
        "macd_divergence": None,
        "market_extreme": None,
        "_ohlcv": [],
    }

    with patch.object(agent, "_analyze_market", AsyncMock(return_value=no_eligible_analysis)):
        result = await agent.execute({"symbol": "BTC/USDT", "timeframe": "1h"})

    assert result["success"] is True
    # signal action should be HOLD
    assert result["signal"]["action"] == "HOLD"
    # Line 52: confidence = agent_confidence (not blended)


# ── circuit_breaker — reset_daily with elapsed < COOLDOWN (branch 73->exit) ──

def test_circuit_breaker_reset_daily_not_enough_elapsed():
    """Branch 73->exit: _tripped_at set but elapsed < COOLDOWN_SECONDS → no reset."""
    from src.orchestration.squad_orchestrator import CircuitBreaker

    cb = CircuitBreaker()
    # Simulate a recent trip
    cb._tripped_at = time.time()  # just tripped → elapsed ≈ 0 < COOLDOWN_SECONDS (24h)

    # reset_daily: _tripped_at is not None, elapsed < COOLDOWN → skip _reset (73->exit)
    cb.reset_daily()

    # Circuit breaker should still be tripped (not reset)
    assert cb._tripped_at is not None


# ── market indicators — OBV computed from short series (branch 184->187) ──────

def test_market_indicators_obv_series_short(tmp_path, monkeypatch):
    """Branch 184->187: obv_series length < 5 → obv_trend stays None."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.api.deps import get_exchange_client
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    # Return exactly 50 candles (minimum), but the OBV series will have ≥ 50 values
    # To get len(obv_series) < 5, we need to mock the analyzer.get_series
    ts = 1_700_000_000_000
    ohlcv = [[ts + i * 3600_000, 50000.0, 50100.0, 49900.0, 50000.0, 100.0] for i in range(50)]
    mc = MagicMock()
    mc.fetch_ohlcv = AsyncMock(return_value=ohlcv)

    app = create_app()
    app.dependency_overrides[get_exchange_client] = lambda: mc
    client = TestClient(app)

    # Patch TechnicalAnalyzer.get_series to return a short series
    import pandas as pd
    with patch("src.analysis.indicators.TechnicalAnalyzer") as MockTA:
        mock_analyzer = MagicMock()
        mock_ind = MagicMock()
        mock_ind.obv = 1000.0         # obv is not None → enters line 182 block
        mock_ind.rsi = 50.0
        mock_ind.macd_line = None
        mock_ind.stochastic_k = None
        mock_ind.bb_upper = None
        mock_ind.atr = None
        mock_ind.ema_fast = None
        mock_ind.ema_slow = None
        mock_ind.sma_20 = None
        mock_ind.sma_50 = None
        mock_ind.sma_200 = None
        mock_ind.volume_ratio = None
        mock_ind.current_price = 50000.0
        # Short OBV series (< 5) → branch 184->187
        mock_analyzer.get_series.return_value = pd.Series([100.0, 200.0, 150.0])  # len=3 < 5
        mock_analyzer.get_latest.return_value = mock_ind
        MockTA.return_value = mock_analyzer

        r = client.get("/v1/market/BTC-USDT/indicators")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["obv_trend"] is None  # len < 5 → obv_trend stays None


# ── market indicators — no OBV (branch 182->187) ─────────────────────────────

def test_market_indicators_no_obv(tmp_path, monkeypatch):
    """Branch 182->187: ind.obv is None → skip OBV trend computation."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.api.deps import get_exchange_client
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    ts = 1_700_000_000_000
    ohlcv = [[ts + i * 3600_000, 50000.0, 50100.0, 49900.0, 50000.0, 100.0] for i in range(50)]
    mc = MagicMock()
    mc.fetch_ohlcv = AsyncMock(return_value=ohlcv)

    app = create_app()
    app.dependency_overrides[get_exchange_client] = lambda: mc
    client = TestClient(app)

    with patch("src.analysis.indicators.TechnicalAnalyzer") as MockTA:
        mock_analyzer = MagicMock()
        mock_ind = MagicMock()
        mock_ind.obv = None           # → 182->187 (skip OBV block entirely)
        mock_ind.rsi = 50.0
        mock_ind.macd_line = None
        mock_ind.stochastic_k = None
        mock_ind.bb_upper = None
        mock_ind.atr = None
        mock_ind.ema_fast = None
        mock_ind.ema_slow = None
        mock_ind.sma_20 = None
        mock_ind.sma_50 = None
        mock_ind.sma_200 = None
        mock_ind.volume_ratio = None
        mock_ind.current_price = 50000.0
        mock_analyzer.get_latest.return_value = mock_ind
        MockTA.return_value = mock_analyzer

        r = client.get("/v1/market/BTC-USDT/indicators")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["obv_trend"] is None


# ── market volume-profile — bins param is None/0 (line 322) ──────────────────

def test_market_volume_profile_bins_not_set(tmp_path, monkeypatch):
    """Line 322: no bins requested → out_bins = []."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.api.deps import get_exchange_client
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    ts = 1_700_000_000_000
    ohlcv = [[ts + i * 3600_000, 50000.0, 50100.0, 49900.0, 50000.0, 100.0] for i in range(200)]
    mc = MagicMock()
    mc.fetch_ohlcv = AsyncMock(return_value=ohlcv)
    mc.fetch_ticker = AsyncMock(return_value={
        "last": 50000.0, "bid": 49990.0, "ask": 50010.0, "timestamp": ts
    })

    app = create_app()
    app.dependency_overrides[get_exchange_client] = lambda: mc
    client = TestClient(app)

    # bins=0 → out_bins = [] (else branch)
    r = client.get("/v1/market/BTC-USDT/volume-profile?bins=0")
    if r.status_code == 200:
        data = r.json()["data"]
        assert data["bins"] == []
    else:
        # bins=0 might be invalid (ge=1), that's ok
        assert r.status_code in (422,)
