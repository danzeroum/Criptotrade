"""Fourth batch of miscellaneous edge-case coverage."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── WeightedConsensusEngine — empty proposals ─────────────────────────────────

def test_consensus_empty_proposals_returns_none():
    """Line 37: not weighted_scores → early return with None decision."""
    from src.consensus.weighted_voting import WeightedConsensusEngine

    engine = WeightedConsensusEngine()
    result = engine.reach_consensus({}, "architecture")
    assert result["decision"] is None
    assert result["consensus_strength"] == 0.0


# ── DesignerAgent.create_design — landing_page hero component ────────────────

@pytest.mark.asyncio
async def test_designer_create_design_landing_page_adds_hero():
    """Line 32: task has 'landing_page' → 'hero' appended to components."""
    from src.agents.designer_agent import DesignerAgent

    agent = DesignerAgent()
    result = await agent.create_design({"description": "product page", "landing_page": True})
    assert "hero" in result["components"]


# ── BaseAgent.log_decision — memory.remember_decision raises ─────────────────

def test_log_decision_memory_exception_is_swallowed():
    """Lines 58-59: memory.remember_decision raises → exception logged, no crash."""
    from src.agents.developer_agent import DeveloperAgent

    agent = DeveloperAgent()
    bad_memory = MagicMock()
    bad_memory.remember_decision.side_effect = RuntimeError("memory error")
    agent.attach_memory(bad_memory)

    # Should not raise despite memory failure
    entry = agent.log_decision({"action": "test"})
    assert entry is not None


# ── _order_to_out — price == stop_loss → rr not computed ─────────────────────

def test_order_to_out_equal_price_stop_skips_rr():
    """Line 27->29: (px - sl) == 0 → rr not computed, still returns OrderOut."""
    from src.hitl.orders import Order
    from src.api.routes.orders import _order_to_out

    order = Order(
        pair="BTC/USDT",
        side="buy",
        quantity=0.1,
        price=50_000.0,
        strategy="test",
        agent_id="a1",
        confidence=0.8,
        reason="test",
        critical=False,
        position_size_pct=2.0,
        stop_loss=50_000.0,   # price == stop_loss → (px - sl) == 0 → rr skipped
        take_profit=52_000.0,
    )
    out = _order_to_out(order)
    assert out is not None
    assert not hasattr(out, "rr") or out.rr is None or "rr" not in out.model_fields_set


# ── MTF indicators — ema_fast None (fix from previous batch) ─────────────────

@pytest.mark.asyncio
async def test_mtf_classify_ema_fast_none_properly_mocked():
    """Line 305: ema_fast is None → 'unknown' (with MIN_CANDLES mocked correctly)."""
    from src.analysis.indicators import MultiTimeframeTrend, TechnicalIndicators

    classifier = MultiTimeframeTrend()

    mock_client = MagicMock()
    mock_client.fetch_ohlcv = AsyncMock(return_value=[
        [i * 1000, 50000.0, 50500.0, 49500.0, 50000.0, 100.0]
        for i in range(52)
    ])

    with patch("src.analysis.indicators.TechnicalAnalyzer") as MockAnalyzer:
        MockAnalyzer.MIN_CANDLES = 50  # must be an int, not MagicMock
        mock_ind = MagicMock(spec=TechnicalIndicators)
        mock_ind.ema_fast = None
        mock_ind.ema_slow = 50_000.0
        MockAnalyzer.return_value.get_latest.return_value = mock_ind

        result = await classifier.classify("BTC/USDT", mock_client)

    assert result.primary == "unknown"


# ── Journal metrics — discipline correlation exception ───────────────────────

def test_journal_metrics_correlation_exception(tmp_path, monkeypatch):
    """Lines 140-141: correlation() raises → pass (result stays None)."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    client = TestClient(create_app())

    # Add 4+ entries where plan_followed has only 1 unique value (xs all same)
    # This means len(set(xs)) == 1 → correlation block skipped
    # To hit exception path (lines 140-141), we need len(set(xs)) > 1 AND correlation raises
    # Simplest: add entries with mixed plan_followed and identical pnl_pct values
    for i in range(4):
        client.post("/v1/journal", json={
            "setup": f"setup {i}",
            "emotion_before": 5,
            "emotion_after": 5,
            "stop_defined": True,
            "plan_followed": i % 2 == 0,  # alternating True/False
            "pnl_pct": 1.0,  # all identical → stdev=0 → correlation may raise
            "note": "test",
        })

    # Should not crash
    response = client.get("/v1/journal/metrics")
    assert response.status_code == 200
