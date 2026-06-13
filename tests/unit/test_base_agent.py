"""Tests for BaseAgent helper methods."""
from __future__ import annotations

import pytest

from src.agents.ops_agent import OpsAgent  # concrete subclass for testing BaseAgent


@pytest.mark.asyncio
async def test_validate_input_false_for_none():
    agent = OpsAgent()
    assert agent.validate_input(None) is False
    assert agent.validate_input({}) is False


@pytest.mark.asyncio
async def test_validate_input_true_for_dict():
    agent = OpsAgent()
    assert agent.validate_input({"key": "value"}) is True


def test_validate_confidence_none_returns_false():
    agent = OpsAgent()
    assert agent.validate_confidence(None) is False


def test_validate_confidence_below_threshold_returns_false():
    agent = OpsAgent()
    assert agent.validate_confidence(0.3) is False  # below default 0.6


def test_validate_confidence_above_threshold_returns_true():
    agent = OpsAgent()
    assert agent.validate_confidence(0.8) is True


def test_log_decision_returns_entry_dict():
    agent = OpsAgent()
    entry = agent.log_decision({"action": "buy", "symbol": "BTC/USDT"})
    assert "timestamp" in entry
    assert "agent" in entry
    assert entry["agent"] == "ops"


def test_attach_memory_sets_memory():
    agent = OpsAgent()

    class _MockMemory:
        def remember_decision(self, agent_type, entry):
            pass

    mock = _MockMemory()
    agent.attach_memory(mock)
    assert agent.memory is mock


def test_log_decision_with_memory_attached():
    """When memory is attached, log_decision calls remember_decision (covers lines 55-57)."""
    agent = OpsAgent()
    calls = []

    class _TrackedMemory:
        def remember_decision(self, agent_type, entry):
            calls.append((agent_type, entry))

    agent.attach_memory(_TrackedMemory())
    agent.log_decision({"test": True})
    assert len(calls) == 1
    assert calls[0][0] == "ops"


def test_log_decision_memory_exception_is_swallowed():
    """Memory failures must not bubble up (covers lines 58-59)."""
    agent = OpsAgent()

    class _FailingMemory:
        def remember_decision(self, *_):
            raise RuntimeError("memory down")

    agent.attach_memory(_FailingMemory())
    # Should not raise
    entry = agent.log_decision({"test": True})
    assert "timestamp" in entry
