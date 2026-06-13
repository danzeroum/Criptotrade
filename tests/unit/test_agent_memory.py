"""Tests for AgentMemorySystem."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.memory.agent_memory import AgentMemorySystem


def test_remember_decision_writes_to_file(tmp_path):
    mem = AgentMemorySystem(storage_dir=tmp_path)
    mem.remember_decision("strategy", {"action": "buy", "timestamp": "2026-01-01T00:00:00"})
    lines = (tmp_path / "agent_memories.jsonl").read_text().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["agent"] == "strategy"
    assert entry["decision"]["action"] == "buy"


def test_remember_decision_multiple_entries(tmp_path):
    mem = AgentMemorySystem(storage_dir=tmp_path)
    for i in range(3):
        mem.remember_decision("risk", {"step": i})
    lines = (tmp_path / "agent_memories.jsonl").read_text().splitlines()
    assert len(lines) == 3


def test_recall_no_collection_returns_empty(tmp_path):
    mem = AgentMemorySystem(storage_dir=tmp_path)
    mem.collection = None
    assert mem.recall("some query") == []


def test_recall_similar_delegates_to_recall(tmp_path):
    mem = AgentMemorySystem(storage_dir=tmp_path)
    mem.collection = None
    assert mem.recall_similar("test", k=3) == []


def test_remember_decision_with_mock_collection(tmp_path):
    """Lines 50-58: when collection is set, calls collection.add."""
    mem = AgentMemorySystem(storage_dir=tmp_path)
    mock_col = MagicMock()
    mem.collection = mock_col

    mem.remember_decision("exec", {"action": "sell", "timestamp": "t1"})

    mock_col.add.assert_called_once()
    call_kwargs = mock_col.add.call_args
    assert "exec" in str(call_kwargs)


def test_remember_decision_collection_add_exception_does_not_raise(tmp_path):
    """Lines 57-58: exception in collection.add is silently swallowed."""
    mem = AgentMemorySystem(storage_dir=tmp_path)
    mock_col = MagicMock()
    mock_col.add.side_effect = RuntimeError("vector db down")
    mem.collection = mock_col

    # Must not raise
    mem.remember_decision("agent", {"action": "hold"})
    lines = (tmp_path / "agent_memories.jsonl").read_text().splitlines()
    assert len(lines) == 1  # file write still happened


def test_recall_with_collection_returns_results(tmp_path):
    """Lines 66-71: recall queries collection when available."""
    mem = AgentMemorySystem(storage_dir=tmp_path)
    mock_col = MagicMock()
    mock_col.query.return_value = [{"doc": "result1"}]
    mem.collection = mock_col

    result = mem.recall("buy signal")
    assert result == [{"doc": "result1"}]
    mock_col.query.assert_called_once_with(query_texts=["buy signal"], n_results=5)


def test_recall_collection_exception_returns_empty(tmp_path):
    """Lines 72-73: collection.query exception → returns []."""
    mem = AgentMemorySystem(storage_dir=tmp_path)
    mock_col = MagicMock()
    mock_col.query.side_effect = RuntimeError("query failed")
    mem.collection = mock_col

    assert mem.recall("test") == []
