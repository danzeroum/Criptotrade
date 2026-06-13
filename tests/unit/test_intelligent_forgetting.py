"""Tests for MemoryStore and IntelligentForgetting."""
from __future__ import annotations

from src.memory.intelligent_forgetting import IntelligentForgetting, MemoryStore


# ── MemoryStore ───────────────────────────────────────────────────────────────

def test_get_all_memories_returns_data():
    store = MemoryStore(data={"k": {"v": 1}})
    assert store.get_all_memories() == {"k": {"v": 1}}


def test_mark_for_removal_deletes_key():
    store = MemoryStore(data={"a": {}, "b": {}})
    store.mark_for_removal("a")
    assert "a" not in store.data
    assert "b" in store.data


def test_mark_for_removal_missing_key_is_noop():
    store = MemoryStore(data={})
    store.mark_for_removal("ghost")  # should not raise


def test_replace_adds_or_updates():
    store = MemoryStore(data={"x": {"old": True}})
    store.replace("x", {"new": True})
    assert store.data["x"] == {"new": True}


def test_execute_cleanup_returns_zero():
    store = MemoryStore(data={"a": {}})
    assert store.execute_cleanup() == 0


# ── IntelligentForgetting ─────────────────────────────────────────────────────

def test_adaptive_forget_removes_low_relevance():
    store = MemoryStore(data={
        "keep": {"relevance": 0.9},
        "forget": {"relevance": 0.05},
    })
    ig = IntelligentForgetting(memory=store)
    removed = ig.adaptive_forget()
    assert removed == 1
    assert "keep" in store.data
    assert "forget" not in store.data


def test_adaptive_forget_keeps_high_relevance():
    store = MemoryStore(data={"a": {"relevance": 0.5}, "b": {"relevance": 1.0}})
    ig = IntelligentForgetting(memory=store)
    removed = ig.adaptive_forget()
    assert removed == 0
    assert len(store.data) == 2


def test_adaptive_forget_no_relevance_key_defaults_to_1():
    """Items without a relevance key default to 1.0 — not removed."""
    store = MemoryStore(data={"x": {"other": "data"}})
    ig = IntelligentForgetting(memory=store)
    removed = ig.adaptive_forget()
    assert removed == 0
    assert "x" in store.data


def test_adaptive_forget_empty_store_returns_zero():
    store = MemoryStore(data={})
    ig = IntelligentForgetting(memory=store)
    assert ig.adaptive_forget() == 0
