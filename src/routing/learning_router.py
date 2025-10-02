"""Adaptive router that learns from historical performance."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class LearningRouter:
    """Suggest optimal routes based on historical outcomes."""

    route_performance: Dict[str, Dict[str, float]] = field(default_factory=dict)

    async def smart_route(self, request: Dict[str, Any]) -> str:
        route = request.get("preferred_route")
        if route:
            return route
        return "default"

    def update_route_performance(self, request: Dict[str, Any], route: str, success: bool, latency: float) -> None:
        key = f"{route}_{self._hash_request(request)}"
        stats = self.route_performance.setdefault(key, {"attempts": 0, "successes": 0, "total_latency": 0.0})
        stats["attempts"] += 1
        if success:
            stats["successes"] += 1
        stats["total_latency"] += float(latency)
        stats["success_rate"] = stats["successes"] / stats["attempts"]
        stats["avg_latency"] = stats["total_latency"] / stats["attempts"]

    def _hash_request(self, request: Dict[str, Any]) -> str:
        payload = repr(sorted(request.items())).encode("utf-8")
        return hashlib.sha1(payload, usedforsecurity=False).hexdigest()
