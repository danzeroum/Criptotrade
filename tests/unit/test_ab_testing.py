"""Regression test: A/B experiment log must be valid JSON lines.

Previously `_log_experiment` wrote `f"{payload}\n"` (a Python repr with single
quotes), producing a file that `json.loads` could not parse. This pins the log
format to real JSON so downstream tooling can consume it.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.evaluation.ab_testing import AgentABTestingFramework


def test_log_experiment_writes_valid_json_lines(tmp_path: Path) -> None:
    ledger = tmp_path / "ab_tests.jsonl"
    framework = AgentABTestingFramework(ledger_path=ledger)

    summary = {
        "winner": "A",
        "scores": {"A": 0.9, "B": 0.7},
        "statistical_significance": 0.2,
    }
    framework._log_experiment(summary)
    framework._log_experiment(summary)

    lines = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        record = json.loads(line)  # must not raise
        assert record["winner"] == "A"
        assert record["scores"] == {"A": 0.9, "B": 0.7}
        assert "timestamp" in record
