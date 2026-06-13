"""Extra coverage for orchestration/unified_orchestrator.py — utility methods."""
from __future__ import annotations

import pytest

from src.orchestration.unified_orchestrator import UnifiedOrchestrator


@pytest.fixture(scope="module")
def orch() -> UnifiedOrchestrator:
    return UnifiedOrchestrator()


# ── _can_parallelize ──────────────────────────────────────────────────────────

def test_can_parallelize_no_deps_normal_action(orch):
    """Returns True when no dependencies and action is not validate/deploy."""
    assert orch._can_parallelize({"action": "implement"}, {}) is True


def test_can_parallelize_with_dependencies_returns_false(orch):
    """Line 168: has dependencies → returns False."""
    assert orch._can_parallelize({"action": "implement", "dependencies": ["step1"]}, {}) is False


def test_can_parallelize_validate_action_returns_false(orch):
    """Line 170: action=validate → returns False."""
    assert orch._can_parallelize({"action": "validate"}, {}) is False


def test_can_parallelize_deploy_action_returns_false(orch):
    """Line 170: action=deploy → returns False."""
    assert orch._can_parallelize({"action": "deploy"}, {}) is False


# ── _select_agent_for_step ────────────────────────────────────────────────────

def test_select_agent_for_unknown_action_returns_developer(orch):
    """Unknown action → fallback to 'developer'."""
    result = orch._select_agent_for_step({"action": "unknown"})
    assert result == "developer"


def test_select_agent_analyze_returns_architect(orch):
    result = orch._select_agent_for_step({"action": "analyze"})
    assert result == "architect"


# ── _update_learning ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_learning_records_route(orch):
    """_update_learning calls router with results."""
    results = [{"route": "fast", "success": True, "duration": 0.5}]
    await orch._update_learning({"task": "test"}, results)
    # Verify router recorded something
    assert len(orch.router.route_performance) >= 1
