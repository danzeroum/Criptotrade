"""Tests for AdaptivePlanner and HierarchicalPlanner."""
from __future__ import annotations

import pytest

from src.planning.adaptive_replanner import AdaptivePlanner
from src.planning.hierarchical_planner import HierarchicalPlanner


# ── AdaptivePlanner ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_trivial_plan_succeeds_on_first_attempt():
    planner = AdaptivePlanner()
    result = await planner.execute_with_replanning({"goal": "trade"})  # no steps key
    assert result["result"]["success"] is True
    assert result["attempts"] == 1


@pytest.mark.asyncio
async def test_execute_plan_with_steps_succeeds():
    planner = AdaptivePlanner()
    result = await planner.execute_with_replanning({"goal": "trade", "steps": ["buy"]})
    assert result["result"]["success"] is True
    assert result["attempts"] == 1


@pytest.mark.asyncio
async def test_execute_plan_always_fails_exhausts_attempts():
    """Subclass that always returns failure to cover replanning loop."""

    class _AlwaysFail(AdaptivePlanner):
        async def _execute_plan(self, plan):
            return {"success": False, "error": "simulated failure"}

    planner = _AlwaysFail(max_replanning_attempts=2)
    result = await planner.execute_with_replanning({"goal": "g", "steps": ["s"]})
    assert result["result"]["success"] is False
    assert result["attempts"] == 2
    assert len(planner.failure_history) == 2


@pytest.mark.asyncio
async def test_analyze_failure_captures_reason():
    planner = AdaptivePlanner()
    ctx = planner._analyze_failure({"error": "oops"}, {"goal": "x"})
    assert ctx["reason"] == "oops"


@pytest.mark.asyncio
async def test_create_recovery_plan_appends_recovery_key():
    planner = AdaptivePlanner()
    recovered = planner._create_recovery_plan({"goal": "g"}, {"reason": "fail"})
    assert "recovery" in recovered
    assert len(recovered["recovery"]) == 1


# ── HierarchicalPlanner ───────────────────────────────────────────────────────

def test_create_plan_returns_dict_with_steps():
    planner = HierarchicalPlanner()
    plan = planner.create_plan("maximize returns")
    assert "goal" in plan
    assert "steps" in plan
    assert isinstance(plan["steps"], list)


def test_create_plan_sets_confidence():
    planner = HierarchicalPlanner()
    plan = planner.create_plan("goal")
    assert plan["confidence"] == pytest.approx(0.8)


def test_decompose_goal_returns_list():
    planner = HierarchicalPlanner()
    steps = planner.decompose_goal("buy BTC")
    assert len(steps) == 1
    assert steps[0]["description"] == "buy BTC"
    assert steps[0]["depth"] == 1


def test_decompose_goal_respects_depth_param():
    planner = HierarchicalPlanner()
    steps = planner.decompose_goal("sell ETH", depth=3)
    assert steps[0]["depth"] == 3


def test_generate_alternatives_returns_two_items():
    planner = HierarchicalPlanner()
    alts = planner.generate_alternatives({"description": "place order"})
    assert len(alts) == 2
    assert "alternativa A" in alts[0]["description"]
    assert "alternativa B" in alts[1]["description"]


def test_evaluate_paths_sets_confidence_on_root():
    planner = HierarchicalPlanner()
    root = {"goal": "g", "steps": []}
    result = planner.evaluate_paths(root)
    assert result["confidence"] == pytest.approx(0.8)
    assert result is root  # mutates and returns same dict


def test_create_plan_substeps_and_alternatives_populated():
    planner = HierarchicalPlanner()
    plan = planner.create_plan("complex goal")
    for step in plan["steps"]:
        assert "substeps" in step
        assert "alternatives" in step
        assert len(step["alternatives"]) == 2
