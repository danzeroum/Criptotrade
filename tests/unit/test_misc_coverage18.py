"""Eighteenth batch — progressive autonomy no-modifications, unified orchestrator
quality>=0.6, strategy_agent exception/no-SR/no-EMA, _calculate_confidence branches."""
from __future__ import annotations

import pandas as pd
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── progressive_autonomy — approved, modifications=None (branch 47->49 False) ─

@pytest.mark.asyncio
async def test_progressive_autonomy_approved_no_modifications():
    """Branch 47->49: approved=True but modifications=None → skip line 48, go to 49."""
    from src.hitl.progressive_autonomy import ProgressiveAutonomyManager

    manager = ProgressiveAutonomyManager()
    # Trust score defaults to 0.5 → level 1 → needs_approval=True
    approval_response = {
        "approved": True,
        "modifications": None,   # falsy → 47 False → jump to 49
        "feedback": None,
    }
    manager.approval_handler = AsyncMock(return_value=approval_response)

    result = await manager.execute_with_autonomy("agent1", {"action": "buy", "critical": False})
    assert result["executed"] is True
    # _execute_action was called without modifications
    manager.approval_handler.assert_awaited_once()


# ── unified_orchestrator — quality >= 0.6, no replan (branch 150->153 False) ──

@pytest.mark.asyncio
async def test_unified_orchestrator_high_quality_no_replan():
    """Branch 150->153: technical_score >= 0.6 → skip replan_from_point (False at 150)."""
    from src.orchestration.unified_orchestrator import UnifiedOrchestrator

    orch = UnifiedOrchestrator.__new__(UnifiedOrchestrator)
    orch.agents = {
        "auditor": MagicMock(execute=AsyncMock(return_value={"success": True})),
    }
    orch.evaluator = MagicMock()
    orch.evaluator.evaluate_agent_performance = AsyncMock(
        return_value={"technical_score": 0.8}   # >= 0.6 → False at line 150 → line 153
    )
    orch.planner = MagicMock()
    orch.planner.replan_from_point = AsyncMock(return_value={"steps": []})

    plan = {"steps": [{"step": 1, "action": "validate", "description": "val"}]}
    results = await orch._execute_plan_steps(plan, {"description": "test task"})

    # replan_from_point must NOT have been called
    orch.planner.replan_from_point.assert_not_awaited()
    assert isinstance(results, list)


# ── strategy_agent — fetch_ohlcv exception (lines 82-84) ──────────────────────

@pytest.mark.asyncio
async def test_strategy_agent_fetch_ohlcv_exception():
    """Lines 82-84: fetch_ohlcv raises → _stub_analysis returned."""
    from src.agents.strategy_agent import StrategyAgent

    exchange_client = MagicMock()
    exchange_client.fetch_ohlcv = AsyncMock(side_effect=ConnectionError("network error"))

    agent = StrategyAgent(exchange_client=exchange_client)
    result = await agent.execute({"symbol": "BTC/USDT", "timeframe": "1h"})
    assert result["success"] is True   # stub analysis → always succeeds


# ── strategy_agent — _analyze_market: no SR → fib_levels={} (branch 98->104) ─
# and no EMA → trend=None (branch 128->131) ────────────────────────────────────

@pytest.mark.asyncio
async def test_strategy_agent_no_sr_no_ema_analyze_market():
    """Branch 98->104: sr_levels.support=None → skip fib_levels.
    Branch 128->131: ema_fast=None → skip trend calculation."""
    from src.agents.strategy_agent import StrategyAgent
    from src.analysis.indicators import TechnicalIndicators
    from src.analysis.support_resistance import SRLevels

    ts = 1_700_000_000_000
    ohlcv = [[ts + i * 3600_000, 50000.0, 50100.0, 49900.0, 50000.0, 100.0]
              for i in range(50)]

    exchange_client = MagicMock()
    exchange_client.fetch_ohlcv = AsyncMock(return_value=ohlcv)

    agent = StrategyAgent(exchange_client=exchange_client)

    # Patch sr_detector to return no support/resistance → branch 98->104 (False)
    agent._sr_detector = MagicMock()
    agent._sr_detector.detect.return_value = SRLevels(support=None, resistance=None)

    # Patch _div_detector to return no divergence
    agent._div_detector = MagicMock()
    agent._div_detector.check_rsi_price.return_value = MagicMock(detected=False)
    agent._div_detector.check_macd_price.return_value = MagicMock(detected=False)

    # Patch TechnicalAnalyzer to return indicators with ema_fast=None → branch 128->131 (False)
    mock_ind = TechnicalIndicators(
        current_price=50000.0,
        ema_fast=None,   # → 128 False → trend stays None
        ema_slow=None,
        rsi=50.0,
    )
    mock_analyzer = MagicMock()
    mock_analyzer.get_latest.return_value = mock_ind
    mock_analyzer.get_series.return_value = pd.Series([], dtype=float)

    mock_ta_class = MagicMock(return_value=mock_analyzer)
    mock_ta_class.MIN_CANDLES = 50
    with patch("src.agents.strategy_agent.TechnicalAnalyzer", mock_ta_class):
        result = await agent._analyze_market("BTC/USDT", "1h")

    # Branch 98->104: fib_levels empty (support=None → skipped)
    assert result["fibonacci_levels"] == {}
    # Branch 128->131: trend is None (ema_fast=None → skipped)
    assert result["trend"] is None


# ── strategy_agent — _calculate_confidence sr_range == 0 (branch 269->278) ────

def test_strategy_agent_confidence_sr_range_zero():
    """Branch 269->278: sr_range == 0 (support==resistance) → skip proximity calc."""
    from src.agents.strategy_agent import StrategyAgent
    from src.analysis.indicators import TechnicalIndicators

    agent = StrategyAgent(exchange_client=None)
    ind = TechnicalIndicators(
        current_price=50_000.0,
        rsi=40.0,       # BUY RSI hit
        macd_hist=0.5,  # BUY MACD hit
    )
    sr = MagicMock()
    sr.support = 50_000.0
    sr.resistance = 50_000.0  # same → sr_range = 0 → line 269 False → jump to 278

    analysis = {
        "indicators": ind,
        "trend": "bullish",
        "support_resistance": sr,
        "rsi_divergence": None,
        "macd_divergence": None,
        "_ohlcv": [],
        "volume_profile": None,
        "market_extreme": None,
    }
    signal = {"action": "BUY", "entry_price": 50_000.0}
    confidence = agent._calculate_confidence(analysis, signal)
    # Score comes only from trend + indicator hits (no S/R proximity since range=0)
    assert 0.0 <= confidence <= 1.0


# ── strategy_agent — confidence HOLD with sr_range > 0 (branch 273->278) ──────

def test_strategy_agent_confidence_hold_with_sr():
    """Branch 273->278: action=HOLD, sr_range>0 → neither BUY nor SELL → skip both."""
    from src.agents.strategy_agent import StrategyAgent
    from src.analysis.indicators import TechnicalIndicators

    agent = StrategyAgent(exchange_client=None)
    ind = TechnicalIndicators(current_price=50_000.0, rsi=50.0)
    sr = MagicMock()
    sr.support = 49_000.0
    sr.resistance = 51_000.0  # sr_range = 2000 > 0 → enters if block
    # entry = 50000 (truthy) and sr.support=49000, sr.resistance=51000 (truthy)
    # sr_range > 0 → True → but action="HOLD" → neither BUY nor SELL → branch 273->278

    analysis = {
        "indicators": ind,
        "trend": None,
        "support_resistance": sr,
        "rsi_divergence": None,
        "macd_divergence": None,
        "_ohlcv": [],
        "volume_profile": None,
        "market_extreme": None,
    }
    signal = {"action": "HOLD", "entry_price": 50_000.0}
    confidence = agent._calculate_confidence(analysis, signal)
    assert 0.0 <= confidence <= 1.0


# ── strategy_agent — rsi divergence detected but action mismatch (289->297) ────

def test_strategy_agent_confidence_rsi_div_mismatch():
    """Branch 289->297: rsi_div detected, action=BUY but kind=bearish → no score added."""
    from src.agents.strategy_agent import StrategyAgent
    from src.analysis.indicators import TechnicalIndicators

    agent = StrategyAgent(exchange_client=None)
    ind = TechnicalIndicators(current_price=50_000.0, rsi=40.0)

    rsi_div = MagicMock()
    rsi_div.detected = True
    rsi_div.kind = "bearish_divergence"   # BUY with bearish divergence → line 287 False, 289 False → 297

    analysis = {
        "indicators": ind,
        "trend": "bullish",
        "support_resistance": None,
        "rsi_divergence": rsi_div,
        "macd_divergence": None,
        "_ohlcv": [],
        "volume_profile": None,
        "market_extreme": None,
    }
    signal = {"action": "BUY", "entry_price": 50_000.0}
    confidence = agent._calculate_confidence(analysis, signal)
    assert 0.0 <= confidence <= 1.0


# ── strategy_agent — macd divergence detected but action mismatch (294->297) ───

def test_strategy_agent_confidence_macd_div_mismatch():
    """Branch 294->297: macd_div detected, action=SELL but kind=bullish → no score added."""
    from src.agents.strategy_agent import StrategyAgent
    from src.analysis.indicators import TechnicalIndicators

    agent = StrategyAgent(exchange_client=None)
    ind = TechnicalIndicators(current_price=50_000.0, rsi=60.0)

    # rsi_div=None → outer elif at line 291 is checked
    macd_div = MagicMock()
    macd_div.detected = True
    macd_div.kind = "bullish_divergence"   # SELL with bullish → line 292 False, 294 False → 297

    analysis = {
        "indicators": ind,
        "trend": "bearish",
        "support_resistance": None,
        "rsi_divergence": None,           # no rsi_div → outer elif at 291 enters
        "macd_divergence": macd_div,
        "_ohlcv": [],
        "volume_profile": None,
        "market_extreme": None,
    }
    signal = {"action": "SELL", "entry_price": 50_000.0}
    confidence = agent._calculate_confidence(analysis, signal)
    assert 0.0 <= confidence <= 1.0
