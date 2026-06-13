"""Extra coverage for ProgressiveAutonomyManager."""
from __future__ import annotations

import pytest

from src.hitl.progressive_autonomy import ProgressiveAutonomyManager


@pytest.mark.asyncio
async def test_execute_with_autonomy_level3_no_approval():
    """Trust score >= 0.8 → level 3 → no approval needed."""
    mgr = ProgressiveAutonomyManager()
    mgr.agent_trust_scores["alpha"] = 0.9  # level 3
    result = await mgr.execute_with_autonomy("alpha", {"action": "trade"})
    assert result["executed"] is True


@pytest.mark.asyncio
async def test_execute_with_autonomy_level2_non_critical_no_approval():
    """Trust score 0.6-0.8 → level 2 → only critical actions need approval."""
    mgr = ProgressiveAutonomyManager()
    mgr.agent_trust_scores["beta"] = 0.7  # level 2
    result = await mgr.execute_with_autonomy("beta", {"action": "trade", "critical": False})
    assert result["executed"] is True


@pytest.mark.asyncio
async def test_execute_with_autonomy_level2_critical_denied():
    """Level 2 + critical → approval requested → no handler → denied."""
    mgr = ProgressiveAutonomyManager()
    mgr.agent_trust_scores["gamma"] = 0.7  # level 2
    result = await mgr.execute_with_autonomy("gamma", {"action": "large_trade", "critical": True})
    assert result["executed"] is False
    assert "Rejected" in result["reason"]


@pytest.mark.asyncio
async def test_execute_with_autonomy_approval_with_modifications():
    """Handler approves with modifications → action is updated before execution."""

    async def _handler(agent, action):
        return {"approved": True, "modifications": {"amount": 999}}

    mgr = ProgressiveAutonomyManager(approval_handler=_handler)
    mgr.agent_trust_scores["delta"] = 0.0  # level 0 → needs approval for everything
    result = await mgr.execute_with_autonomy("delta", {"action": "buy", "amount": 1})
    assert result["executed"] is True


@pytest.mark.asyncio
async def test_execute_records_action_and_adjusts_trust():
    """execute_with_autonomy records action in history and updates trust score."""
    mgr = ProgressiveAutonomyManager()
    mgr.agent_trust_scores["eps"] = 0.9  # skip approval
    await mgr.execute_with_autonomy("eps", {"action": "buy"})
    assert len(mgr.action_history) == 1
    assert mgr.action_history[0]["agent"] == "eps"
    # Trust score should have increased slightly (success)
    assert mgr.agent_trust_scores["eps"] > 0.9


def test_needs_human_approval_level0_always_true():
    """Level 0 → any action needs approval."""
    mgr = ProgressiveAutonomyManager()
    mgr.agent_trust_scores["zeta"] = 0.1  # score < 0.4 → level 0
    assert mgr.needs_human_approval("zeta", critical=False) is True
    assert mgr.needs_human_approval("zeta", critical=True) is True


def test_needs_human_approval_level1_always_true():
    """Level 1 (0.4 ≤ score < 0.6) → approval needed regardless of critical."""
    mgr = ProgressiveAutonomyManager()
    mgr.agent_trust_scores["eta"] = 0.5
    assert mgr.needs_human_approval("eta", critical=False) is True


def test_needs_human_approval_level3_always_false():
    """Level 3 (score >= 0.8) → never needs approval."""
    mgr = ProgressiveAutonomyManager()
    mgr.agent_trust_scores["theta"] = 0.95
    assert mgr.needs_human_approval("theta", critical=True) is False


@pytest.mark.asyncio
async def test_request_human_approval_no_handler_returns_denied():
    """No approval_handler → fail-closed → approved=False."""
    mgr = ProgressiveAutonomyManager(approval_handler=None)
    resp = await mgr._request_human_approval("agent", {"action": "x"})
    assert resp["approved"] is False
    assert "fail-closed" in resp["feedback"]


@pytest.mark.asyncio
async def test_request_human_approval_with_handler():
    """approval_handler is called and its result is returned."""

    async def _accept(agent, action):
        return {"approved": True, "modifications": None}

    mgr = ProgressiveAutonomyManager(approval_handler=_accept)
    resp = await mgr._request_human_approval("a", {})
    assert resp["approved"] is True
