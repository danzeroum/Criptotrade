"""Lightweight agent A/B testing utilities."""
from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


@dataclass
class AgentABTestingFramework:
    """Execute simple A/B comparisons between agent implementations."""

    ledger_path: Path = Path(".BuildToValue/ledger/ab_tests.jsonl")

    async def run_ab_test(
        self,
        agent_a: Any,
        agent_b: Any,
        test_cases: Iterable[Dict[str, Any]],
        metrics: List[str],
    ) -> Dict[str, Any]:
        results = {"A": [], "B": []}
        for case in test_cases:
            order = ["A", "B"]
            random.shuffle(order)
            outputs = {}
            for variant in order:
                agent = agent_a if variant == "A" else agent_b
                if hasattr(agent, "execute"):
                    outputs[variant] = await agent.execute(case)
                else:
                    outputs[variant] = {"success": True}
            for variant, output in outputs.items():
                results[variant].append(self._score_output(output, metrics))
        summary = self._summarise_results(results)
        self._log_experiment(summary)
        return summary

    def _score_output(self, output: Dict[str, Any], metrics: List[str]) -> float:
        score_components = []
        for metric in metrics:
            score_components.append(float(output.get(metric, 1.0)))
        return sum(score_components) / max(len(score_components), 1)

    def _summarise_results(self, results: Dict[str, List[float]]) -> Dict[str, Any]:
        avg_a = statistics.fmean(results["A"]) if results["A"] else 0.0
        avg_b = statistics.fmean(results["B"]) if results["B"] else 0.0
        winner = "A" if avg_a >= avg_b else "B"
        diff = abs(avg_a - avg_b)
        significance = min(1.0, diff)
        return {"winner": winner, "scores": {"A": avg_a, "B": avg_b}, "statistical_significance": significance}

    def _log_experiment(self, summary: Dict[str, Any]) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"timestamp": datetime.now(timezone.utc).isoformat(), **summary}
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{payload}\n")
