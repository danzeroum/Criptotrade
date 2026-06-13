"""Coverage for routing/learning_router.py — smart_route and update_route_performance."""
from __future__ import annotations

import pytest

from src.routing.learning_router import LearningRouter


@pytest.mark.asyncio
async def test_smart_route_with_preferred_route():
    """Lines 17-18: preferred_route present → returns it directly."""
    router = LearningRouter()
    result = await router.smart_route({"preferred_route": "fast_lane", "other": "data"})
    assert result == "fast_lane"


@pytest.mark.asyncio
async def test_smart_route_without_preferred_route():
    """Line 19: no preferred_route → returns 'default'."""
    router = LearningRouter()
    result = await router.smart_route({"action": "buy"})
    assert result == "default"


def test_update_route_performance_success():
    """Line 25->26: success=True → successes incremented."""
    router = LearningRouter()
    router.update_route_performance({"action": "buy"}, "route_a", True, 0.5)
    key = next(iter(router.route_performance))
    assert router.route_performance[key]["successes"] == 1
    assert router.route_performance[key]["success_rate"] == 1.0


def test_update_route_performance_failure():
    """Line 25->27: success=False → successes not incremented."""
    router = LearningRouter()
    router.update_route_performance({"action": "sell"}, "route_b", False, 1.0)
    key = next(iter(router.route_performance))
    assert router.route_performance[key]["successes"] == 0
    assert router.route_performance[key]["success_rate"] == 0.0


def test_update_route_performance_accumulates():
    """Multiple calls accumulate correctly."""
    router = LearningRouter()
    req = {"task": "test"}
    router.update_route_performance(req, "route_c", True, 0.3)
    router.update_route_performance(req, "route_c", False, 0.7)
    key = next(iter(router.route_performance))
    stats = router.route_performance[key]
    assert stats["attempts"] == 2
    assert stats["successes"] == 1
    assert stats["success_rate"] == 0.5
    assert abs(stats["avg_latency"] - 0.5) < 1e-9
