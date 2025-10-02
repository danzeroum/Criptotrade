"""Weighted consensus utilities for multi-agent decisions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class WeightedConsensusEngine:
    """Compute consensus using expertise-weighted voting."""

    agent_weights: Dict[str, Dict[str, float]] = field(
        default_factory=lambda: {
            "architect": {"architecture": 0.9, "security": 0.7},
            "developer": {"architecture": 0.6, "implementation": 0.95, "testing": 0.8},
            "auditor": {"security": 0.95, "quality": 0.85},
            "designer": {"ui": 0.95, "ux": 0.9},
            "ops": {"infrastructure": 0.9, "deployment": 0.9},
        }
    )

    def reach_consensus(self, proposals: Dict[str, Dict[str, float]], decision_type: str) -> Dict[str, object]:
        """Aggregate proposals and return the winning option and consensus strength."""

        weighted_scores: Dict[str, Dict[str, float]] = {}
        for agent, proposal in proposals.items():
            weight = self.agent_weights.get(agent, {}).get(decision_type, 0.5)
            confidence = float(proposal.get("confidence", 0.5))
            score = weight * confidence
            weighted_scores[agent] = {
                "weighted_score": score,
                "raw_weight": weight,
                "raw_confidence": confidence,
            }

        if not weighted_scores:
            return {"decision": None, "consensus_strength": 0.0, "decision_maker": None, "dissenting_opinions": []}

        winner_agent = max(weighted_scores, key=lambda name: weighted_scores[name]["weighted_score"])
        total = sum(entry["weighted_score"] for entry in weighted_scores.values()) or 1.0
        consensus_strength = weighted_scores[winner_agent]["weighted_score"] / total
        dissent = [
            {"agent": agent, "score": info["weighted_score"]}
            for agent, info in weighted_scores.items()
            if agent != winner_agent
        ]
        return {
            "decision": proposals[winner_agent],
            "consensus_strength": consensus_strength,
            "decision_maker": winner_agent,
            "dissenting_opinions": dissent,
        }
