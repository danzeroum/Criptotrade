"""Tests for AgentABTestingFramework."""
from __future__ import annotations

import pytest

from src.evaluation.ab_testing import AgentABTestingFramework


class _StaticAgent:
    """Returns a preset output dict."""
    def __init__(self, output: dict):
        self._output = output

    async def execute(self, case: dict) -> dict:
        return self._output


class _NoExecuteAgent:
    """Agent with no execute method — framework falls back to {'success': True}."""
    pass


# ── _score_output ─────────────────────────────────────────────────────────────

def test_score_output_single_metric():
    fw = AgentABTestingFramework.__new__(AgentABTestingFramework)
    assert fw._score_output({"profit": 2.5}, ["profit"]) == pytest.approx(2.5)


def test_score_output_missing_metric_defaults_to_1():
    fw = AgentABTestingFramework.__new__(AgentABTestingFramework)
    score = fw._score_output({}, ["missing_metric"])
    assert score == pytest.approx(1.0)


def test_score_output_multiple_metrics_averaged():
    fw = AgentABTestingFramework.__new__(AgentABTestingFramework)
    score = fw._score_output({"a": 1.0, "b": 3.0}, ["a", "b"])
    assert score == pytest.approx(2.0)


def test_score_output_empty_metrics_returns_0():
    fw = AgentABTestingFramework.__new__(AgentABTestingFramework)
    assert fw._score_output({"a": 5.0}, []) == pytest.approx(0.0)


# ── _summarise_results ────────────────────────────────────────────────────────

def test_summarise_results_a_wins():
    fw = AgentABTestingFramework.__new__(AgentABTestingFramework)
    result = fw._summarise_results({"A": [0.9, 0.8], "B": [0.5, 0.4]})
    assert result["winner"] == "A"
    assert result["scores"]["A"] > result["scores"]["B"]


def test_summarise_results_b_wins():
    fw = AgentABTestingFramework.__new__(AgentABTestingFramework)
    result = fw._summarise_results({"A": [0.2], "B": [0.9]})
    assert result["winner"] == "B"


def test_summarise_results_empty_lists():
    fw = AgentABTestingFramework.__new__(AgentABTestingFramework)
    result = fw._summarise_results({"A": [], "B": []})
    assert result["winner"] == "A"  # tie → A wins
    assert result["scores"]["A"] == pytest.approx(0.0)
    assert result["statistical_significance"] == pytest.approx(0.0)


def test_summarise_results_significance_capped_at_1():
    fw = AgentABTestingFramework.__new__(AgentABTestingFramework)
    result = fw._summarise_results({"A": [5.0], "B": [0.0]})
    assert result["statistical_significance"] <= 1.0


# ── run_ab_test ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_ab_test_with_execute_agents(tmp_path):
    fw = AgentABTestingFramework(ledger_path=tmp_path / "ab.jsonl")
    agent_a = _StaticAgent({"profit": 0.8})
    agent_b = _StaticAgent({"profit": 0.3})
    cases = [{"id": 1}, {"id": 2}]
    result = await fw.run_ab_test(agent_a, agent_b, cases, metrics=["profit"])
    assert result["winner"] in ("A", "B")
    assert "scores" in result
    assert "statistical_significance" in result
    # Log file must exist
    assert (tmp_path / "ab.jsonl").exists()


@pytest.mark.asyncio
async def test_run_ab_test_no_execute_falls_back(tmp_path):
    fw = AgentABTestingFramework(ledger_path=tmp_path / "ab2.jsonl")
    agent_a = _NoExecuteAgent()
    agent_b = _NoExecuteAgent()
    result = await fw.run_ab_test(agent_a, agent_b, [{"x": 1}], metrics=["success"])
    # Both agents fallback to {"success": True} → score 1.0 each → A wins on tie
    assert result["winner"] == "A"


@pytest.mark.asyncio
async def test_run_ab_test_empty_cases(tmp_path):
    fw = AgentABTestingFramework(ledger_path=tmp_path / "ab3.jsonl")
    agent_a = _StaticAgent({"v": 1.0})
    agent_b = _StaticAgent({"v": 1.0})
    result = await fw.run_ab_test(agent_a, agent_b, [], metrics=["v"])
    assert result["scores"]["A"] == pytest.approx(0.0)
    assert result["scores"]["B"] == pytest.approx(0.0)
