"""Fifth batch of miscellaneous edge-case coverage."""
from __future__ import annotations

import pytest


# ── RiskAgent._reflect_on_validation — missed_anything → True ────────────────

@pytest.mark.asyncio
async def test_risk_agent_reflect_approved_with_many_warnings():
    """Lines 99-100: validation approved + >2 warnings → missed_anything=True."""
    from src.agents.risk_agent import RiskAgent

    agent = RiskAgent()
    validation = {
        "approved": True,
        "issues": [],
        "warnings": ["w1", "w2", "w3"],  # > 2 warnings
        "confidence": 0.9,
    }
    reflection = await agent._reflect_on_validation(validation)
    assert reflection["missed_anything"] is True
    assert len(reflection["suggestions"]) > 0


# ── Journal metrics — all plan_followed=True → len(set(xs)) == 1 → 137->143 ──

def test_journal_metrics_uniform_plan_followed_skips_correlation(tmp_path, monkeypatch):
    """Line 137->143: all entries have same plan_followed → len(set(xs))==1 → no correlation."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    client = TestClient(create_app())

    # Add 4 entries with same plan_followed=True and different pnl_pct
    for pnl in [1.0, 2.0, -1.0, 0.5]:
        client.post("/v1/journal", json={
            "setup": "test",
            "emotion_before": 5,
            "emotion_after": 5,
            "stop_defined": True,
            "plan_followed": True,  # all same → len(set(xs)) == 1
            "pnl_pct": pnl,
            "note": "",
        })

    response = client.get("/v1/journal/metrics")
    assert response.status_code == 200
    data = response.json()["data"]
    # Correlation block skipped; discipline_correlation should be None
    assert data["discipline_correlation"] is None


# ── ArchitectAgent.create_plan — no "cache" in recommendation ─────────────────

@pytest.mark.asyncio
async def test_architect_create_plan_no_cache_in_recommendation():
    """Line 109->112: recommendation without 'cache' → Caching Layer not added."""
    from src.agents.architect_agent import ArchitectAgent

    agent = ArchitectAgent()
    reasoning = {
        "recommendation": "Use microservices with load balancing",
        "applicable_patterns": ["CQRS", "Event Sourcing"],
    }
    result = await agent.create_plan({"description": "build API"}, reasoning)
    assert "Caching Layer" not in result["components"]
    assert "API Gateway" in result["components"]


@pytest.mark.asyncio
async def test_architect_create_plan_with_cache_in_recommendation():
    """Line 109->110: recommendation contains 'cache' → Caching Layer appended."""
    from src.agents.architect_agent import ArchitectAgent

    agent = ArchitectAgent()
    reasoning = {"recommendation": "Add a Redis cache layer for performance", "applicable_patterns": []}
    result = await agent.create_plan({"description": "build fast API"}, reasoning)
    assert "Caching Layer" in result["components"]


# ── DesignerAgent.execute — invalid task raises ───────────────────────────────

@pytest.mark.asyncio
async def test_designer_execute_invalid_task_raises():
    """Line 19: validate_input fails → ValueError raised."""
    from src.agents.designer_agent import DesignerAgent

    agent = DesignerAgent()
    with pytest.raises(ValueError, match="Invalid design task payload"):
        await agent.execute(None)


# ── Config API — patch agent config with known agent ─────────────────────────

def test_config_patch_known_agent(tmp_path, monkeypatch):
    """Line 96: agent_id in AGENT_PARAMS → update called."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    client = TestClient(create_app())

    response = client.patch(
        "/v1/agents/strategy/config",
        json={"autonomy_level": 3},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == "strategy"
