"""Hierarchical planner inspired by Tree-of-Thoughts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class HierarchicalPlanner:
    """Create multi-level plans for complex goals."""

    def create_plan(self, goal: str, max_depth: int = 3) -> Dict[str, Any]:
        root = {"goal": goal, "steps": [], "alternatives": [], "confidence": 0.0}
        main_steps = self.decompose_goal(goal)
        for step in main_steps:
            substeps = self.decompose_goal(step["description"], depth=2)
            step["substeps"] = substeps
            step["alternatives"] = self.generate_alternatives(step)
        root["steps"] = main_steps
        best = self.evaluate_paths(root)
        return best

    def decompose_goal(self, goal: str, depth: int = 1) -> List[Dict[str, Any]]:
        return [
            {"description": goal, "depth": depth, "confidence": 0.7},
        ]

    def generate_alternatives(self, step: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {"description": step["description"] + " (alternativa A)", "confidence": 0.6},
            {"description": step["description"] + " (alternativa B)", "confidence": 0.5},
        ]

    def evaluate_paths(self, root: Dict[str, Any]) -> Dict[str, Any]:
        root["confidence"] = 0.8
        return root
