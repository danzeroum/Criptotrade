"""Tests for ContinuousEvaluator."""
from __future__ import annotations

import pytest

from src.evaluation.continuous_eval import ContinuousEvaluator


class _Completed:
    completed = True
    resource_usage = 1.0
    guardrail_violations = 0


class _Failed:
    completed = False
    resource_usage = 2.0
    guardrail_violations = 3


class _NoAttrs:
    pass


def test_evaluate_trajectory_completed():
    ev = ContinuousEvaluator({"resource_target": 1.0})
    scores = ev.evaluate_trajectory(_Completed())
    assert scores["task_completion"] == pytest.approx(1.0)
    assert scores["efficiency"] == pytest.approx(1.0)
    assert scores["safety"] == pytest.approx(1.0)


def test_evaluate_trajectory_failed():
    ev = ContinuousEvaluator({"resource_target": 1.0})
    scores = ev.evaluate_trajectory(_Failed())
    assert scores["task_completion"] == pytest.approx(0.0)
    # efficiency = target / used = 1.0 / 2.0 = 0.5
    assert scores["efficiency"] == pytest.approx(0.5)
    assert scores["safety"] == pytest.approx(0.0)  # violations > 0


def test_check_goal_achievement_uses_completed_attr():
    ev = ContinuousEvaluator({})
    assert ev.check_goal_achievement(_Completed()) == pytest.approx(1.0)
    assert ev.check_goal_achievement(_Failed()) == pytest.approx(0.0)
    assert ev.check_goal_achievement(_NoAttrs()) == pytest.approx(0.0)


def test_measure_resource_usage_zero_target():
    ev = ContinuousEvaluator({"resource_target": 0})
    assert ev.measure_resource_usage(_Completed()) == pytest.approx(0.0)


def test_measure_resource_usage_no_resource_key():
    ev = ContinuousEvaluator({})
    # resource_target defaults to 1.0; resource_usage defaults to 1.0
    assert ev.measure_resource_usage(_NoAttrs()) == pytest.approx(1.0)


def test_measure_resource_usage_clamped_to_1():
    ev = ContinuousEvaluator({"resource_target": 10.0})
    score = ev.measure_resource_usage(_Completed())  # usage=1.0, target=10 → 10.0, clamped to 1
    assert score == pytest.approx(1.0)


def test_validate_guardrail_compliance_zero_violations():
    ev = ContinuousEvaluator({})
    assert ev.validate_guardrail_compliance(_Completed()) == pytest.approx(1.0)


def test_validate_guardrail_compliance_with_violations():
    ev = ContinuousEvaluator({})
    assert ev.validate_guardrail_compliance(_Failed()) == pytest.approx(0.0)
