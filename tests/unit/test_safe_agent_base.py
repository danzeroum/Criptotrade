"""Tests for SafeAgentBase, GuardrailSuite and related helpers."""
from __future__ import annotations

import pytest

from src.core.safe_agent_base import (
    AgentExecution,
    EthicalBoundaryChecker,
    GuardrailSuite,
    InputSanitizer,
    MemoryManager,
    OutputValidator,
    Plan,
    PlanCreation,
    ResourceLimiter,
    SafeAgentBase,
)


# ── GuardrailSuite ────────────────────────────────────────────────────────────

def test_guardrail_suite_passes_valid_pattern():
    suite = GuardrailSuite([InputSanitizer(), OutputValidator()])
    assert suite.validate_pattern_safety("market_analysis") is True


def test_guardrail_suite_fails_empty_pattern():
    suite = GuardrailSuite([InputSanitizer()])
    assert suite.validate_pattern_safety("") is False


# ── SafeAgentBase: add_capability / list_capabilities ────────────────────────

def test_add_capability_valid():
    agent = SafeAgentBase()
    agent.add_capability("data_fetching")
    assert "data_fetching" in agent.list_capabilities()


def test_add_capability_invalid_raises():
    """Line 74: empty pattern fails guardrails → ValueError."""

    class _AlwaysFail:
        name = "always_fail"
        def validate(self, pattern: str) -> bool:
            return False

    agent = SafeAgentBase()
    agent.guardrails = GuardrailSuite([_AlwaysFail()])
    with pytest.raises(ValueError, match="failed safety validation"):
        agent.add_capability("anything")


def test_list_capabilities_empty_initially():
    agent = SafeAgentBase()
    assert agent.list_capabilities() == []


# ── SafeAgentBase: create_plan ────────────────────────────────────────────────

def test_create_plan_without_memory_capability():
    """Lines 83-94: 'memory' not in capabilities → memory_context=None."""
    agent = SafeAgentBase()
    plan = agent.create_plan("analyse market")
    assert isinstance(plan, Plan)
    assert plan.creation.memory_accessed is False
    assert plan.creation.memory_context is None


def test_create_plan_with_memory_capability():
    """Lines 85-87: 'memory' in capabilities → memory.recall called."""
    agent = SafeAgentBase()
    agent.add_capability("memory")
    plan = agent.create_plan("analyse BTC")
    assert plan.creation.memory_accessed is True
    assert plan.creation.memory_context is not None


# ── SafeAgentBase: execute ────────────────────────────────────────────────────

def test_execute_returns_agent_execution():
    """Lines 99-103: execute returns AgentExecution."""
    agent = SafeAgentBase()
    result = agent.execute("backtest strategy")
    assert isinstance(result, AgentExecution)
    assert result.completed is True
    assert result.guardrail_violations == 0
    assert "backtest strategy" in result.output


def test_execute_with_explicit_context():
    """Line 100: context parameter overrides plan's memory_context."""
    agent = SafeAgentBase()
    result = agent.execute("task", context="explicit context")
    assert result.context == "explicit context"


def test_execute_resource_usage_scales_with_capabilities():
    """resource_usage = max(1.0, len(capabilities))."""
    agent = SafeAgentBase()
    agent.add_capability("cap_a")
    agent.add_capability("cap_b")
    result = agent.execute("task")
    assert result.resource_usage == pytest.approx(2.0)


def test_execute_resource_usage_minimum_1():
    agent = SafeAgentBase()
    result = agent.execute("task")  # no capabilities
    assert result.resource_usage == pytest.approx(1.0)


# ── AgentExecution.to_dict ────────────────────────────────────────────────────

def test_agent_execution_to_dict():
    """Line 134-136: to_dict returns serialisable mapping."""
    exec_ = AgentExecution(
        task="t", context=None, completed=True,
        resource_usage=1.0, guardrail_violations=0, output="out"
    )
    d = exec_.to_dict()
    assert d["task"] == "t"
    assert d["completed"] is True


# ── MemoryManager ─────────────────────────────────────────────────────────────

def test_memory_manager_recall_returns_context():
    """Lines 139: recall sets and returns a context string."""
    mm = MemoryManager()
    ctx = mm.recall("trade BTC")
    assert "trade BTC" in ctx


def test_memory_manager_was_accessed_true():
    """Line 158: was_accessed_during True when recall matches."""
    mm = MemoryManager()
    mm.recall("task X")
    pc = PlanCreation(task="task X", memory_context=mm._last_context, memory_accessed=True)
    assert mm.was_accessed_during(pc) is True


def test_memory_manager_was_accessed_false_when_not_accessed():
    mm = MemoryManager()
    pc = PlanCreation(task="task Y", memory_context=None, memory_accessed=False)
    assert mm.was_accessed_during(pc) is False
