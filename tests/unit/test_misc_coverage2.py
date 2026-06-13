"""Second batch of miscellaneous edge-case coverage."""
from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest


# ── backtest API route — BUY signal ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_backtest_simple_strategy_buy():
    """Line 98: rsi < 30 and macd_hist > 0 → BUY signal."""
    from src.api.routes.backtest import _SimpleStrategy

    strat = _SimpleStrategy()
    result = await strat.analyze({
        "indicators": {"rsi": 25.0, "macd_hist": 0.5, "atr": 500.0},
        "current_price": 50_000.0,
    })
    assert result["action"] == "buy"
    assert "stop_loss" in result
    assert "take_profit" in result


# ── AdaptivePlanner.analyze_failure — timeout / memory / unknown branches ─────

def test_analyze_failure_timeout():
    """Line 159: 'timeout' in error message → reason=timeout."""
    from src.planning.adaptive_planner import AdaptivePlanner

    planner = AdaptivePlanner()
    result = planner.analyze_failure(RuntimeError("connection timeout"), {"plan_id": "p1"})
    assert result["reason"] == "timeout"
    assert result["suggestion"] == "increase_timeout"


def test_analyze_failure_memory():
    """Line 161: 'memory' in error message → reason=memory_limit."""
    from src.planning.adaptive_planner import AdaptivePlanner

    planner = AdaptivePlanner()
    result = planner.analyze_failure(MemoryError("out of memory"), {"plan_id": "p2"})
    assert result["reason"] == "memory_limit"
    assert result["suggestion"] == "optimise_memory"


def test_analyze_failure_unknown():
    """Lines 155-156: no keyword match → reason=unknown."""
    from src.planning.adaptive_planner import AdaptivePlanner

    planner = AdaptivePlanner()
    result = planner.analyze_failure(ValueError("unexpected error"), {})
    assert result["reason"] == "unknown"
    assert result["suggestion"] == "investigate"


# ── detect_market_extreme — None inputs ─────────────────────────────────────

def test_detect_market_extreme_none_rsi():
    """Line 75: rsi=None → returns None."""
    from src.analysis.regime_detector import detect_market_extreme

    assert detect_market_extreme(rsi=None, volume_ratio=2.5) is None


def test_detect_market_extreme_none_volume():
    """Line 75: volume_ratio=None → returns None."""
    from src.analysis.regime_detector import detect_market_extreme

    assert detect_market_extreme(rsi=80.0, volume_ratio=None) is None


# ── HITLConfigStore._count_today — invalid timestamp ─────────────────────────

def test_count_today_invalid_timestamp_skipped():
    """Lines 152-153: ValueError on fromisoformat → continue (entry skipped)."""
    from src.hitl.config import HITLConfigStore

    today = date(2024, 1, 15)
    approvals = [
        {"timestamp": "NOT_A_DATE", "data": {"approved": True}},
        {"timestamp": "2024-01-15T10:00:00+00:00", "data": {"approved": True}},
    ]
    approved, rejected = HITLConfigStore._count_today(approvals, today)
    # Bad timestamp is skipped, only the valid one is counted
    assert approved == 1
    assert rejected == 0


# ── DCAOptimizedStrategy._confidence — sideways trend ──────────────────────

def test_dca_confidence_sideways_trend():
    """Line 144->145: trend=sideways → +0.10 score."""
    from src.strategies.dca_optimized import DCAOptimizedStrategy

    strat = DCAOptimizedStrategy()
    score = strat._calculate_confidence(trend="sideways", indicators={}, volume_ok=False)
    assert score == pytest.approx(0.60)  # 0.50 + 0.10


def test_dca_confidence_uptrend():
    """trend=uptrend → no trend bonus (not downtrend/sideways)."""
    from src.strategies.dca_optimized import DCAOptimizedStrategy

    strat = DCAOptimizedStrategy()
    score = strat._calculate_confidence(trend="uptrend", indicators={}, volume_ok=False)
    assert score == pytest.approx(0.50)  # base only


# ── MCPServer.handle_request — dict payload already extracted by getattr ──────

def test_mcp_handle_request_object_with_payload_attribute():
    """Lines 54->57: payload found via getattr (not None) → dict check skipped."""
    from src.protocols.mcp_server import MCPServer

    class AgentStub:
        def execute(self, task):
            return {"done": True}

    class ExecuteRequest:
        type = "execute"
        payload = {"task": "implement auth"}

    server = MCPServer(AgentStub())
    result = server.handle_request(ExecuteRequest())
    assert result == {"done": True}


def test_mcp_handle_request_dict_with_non_dict_payload():
    """Lines 60->63: payload is not a dict → execute(payload) called."""
    from src.protocols.mcp_server import MCPServer

    class AgentStub:
        def execute(self, arg):
            return f"executed: {arg}"

    server = MCPServer(AgentStub())
    result = server.handle_request({"type": "execute", "payload": "run tests"})
    assert "executed" in result
