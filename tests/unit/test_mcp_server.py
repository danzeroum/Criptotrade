"""Tests for MCPServer and AgentOrchestrator."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.protocols.mcp_server import MCPServer


# ── Helper agent stubs ────────────────────────────────────────────────────────

class _CapabilityAgent:
    name = "test-agent"
    endpoint = "mcp://test"

    def list_capabilities(self):
        return ["market_data", "signals"]

    def execute(self, *args, **kwargs):
        return {"result": "executed", "args": args, "kwargs": kwargs}


class _AttrAgent:
    """Agent with capabilities as attribute (not list_capabilities method)."""
    capabilities = ["basic_cap"]


class _NoCapAgent:
    """Agent with neither list_capabilities nor capabilities."""
    pass


# ── MCPServer.discover_capabilities ──────────────────────────────────────────

def test_discover_uses_list_capabilities_method():
    server = MCPServer(_CapabilityAgent())
    caps = server.discover_capabilities()
    assert "market_data" in caps
    assert "signals" in caps


def test_discover_falls_back_to_capabilities_attr():
    server = MCPServer(_AttrAgent())
    assert "basic_cap" in server.discover_capabilities()


def test_discover_returns_empty_for_no_capabilities():
    server = MCPServer(_NoCapAgent())
    assert server.discover_capabilities() == []


# ── MCPServer.get_endpoint ────────────────────────────────────────────────────

def test_get_endpoint_uses_agent_attribute():
    server = MCPServer(_CapabilityAgent())
    assert server.get_endpoint() == "mcp://test"


def test_get_endpoint_default_when_no_attribute():
    server = MCPServer(_NoCapAgent())
    assert server.get_endpoint() == "mcp://localhost"


# ── MCPServer.publish_agent_card ──────────────────────────────────────────────

def test_publish_agent_card_returns_required_fields():
    server = MCPServer(_CapabilityAgent())
    card = server.publish_agent_card()
    assert card["name"] == "test-agent"
    assert isinstance(card["skills"], list)
    assert "endpoint" in card


def test_publish_agent_card_anonymous_name_when_missing():
    server = MCPServer(_NoCapAgent())
    card = server.publish_agent_card()
    assert card["name"] == "anonymous-agent"


# ── MCPServer.handle_request ──────────────────────────────────────────────────

def test_handle_request_discover_returns_card():
    server = MCPServer(_CapabilityAgent())
    result = server.handle_request({"type": "discover"})
    assert "name" in result
    assert "skills" in result


def test_handle_request_discover_via_object_attr():
    server = MCPServer(_CapabilityAgent())
    req = MagicMock()
    req.type = "discover"
    result = server.handle_request(req)
    assert "name" in result


def test_handle_request_execute_with_dict_payload():
    class _SyncAgent:
        name = "sync"
        def execute(self, action="noop", **kw):
            return {"action": action}
        def list_capabilities(self):
            return []

    server = MCPServer(_SyncAgent())
    result = server.handle_request({"type": "execute", "payload": {"action": "buy"}})
    assert result["action"] == "buy"


def test_handle_request_execute_with_none_payload():
    class _SyncAgent:
        def execute(self, x=""):
            return f"exec:{x}"
        def list_capabilities(self):
            return []

    server = MCPServer(_SyncAgent())
    result = server.handle_request({"type": "execute", "payload": None})
    assert result == "exec:"


def test_handle_request_execute_with_non_dict_payload():
    class _SyncAgent:
        def execute(self, x):
            return f"exec:{x}"
        def list_capabilities(self):
            return []

    server = MCPServer(_SyncAgent())
    result = server.handle_request({"type": "execute", "payload": "hello"})
    assert result == "exec:hello"


def test_handle_request_execute_returns_dataclass_as_dict():
    from dataclasses import dataclass

    @dataclass
    class _Result:
        value: int = 42

    class _DCAgent:
        def execute(self, **_kw):
            return _Result()
        def list_capabilities(self):
            return []

    server = MCPServer(_DCAgent())
    result = server.handle_request({"type": "execute", "payload": {}})
    assert result == {"value": 42}


def test_handle_request_execute_returns_to_dict_result():
    class _DictableResult:
        def to_dict(self):
            return {"status": "ok"}

    class _DAgent:
        def execute(self, **_):
            return _DictableResult()
        def list_capabilities(self):
            return []

    server = MCPServer(_DAgent())
    result = server.handle_request({"type": "execute", "payload": {}})
    assert result == {"status": "ok"}


def test_handle_request_execute_no_execute_method_raises():
    server = MCPServer(_NoCapAgent())
    with pytest.raises(AttributeError, match="execute"):
        server.handle_request({"type": "execute", "payload": "x"})


def test_handle_request_unknown_type_raises():
    server = MCPServer(_CapabilityAgent())
    with pytest.raises(ValueError, match="Unsupported"):
        server.handle_request({"type": "unknown_type"})


# ── AgentOrchestrator ─────────────────────────────────────────────────────────

def test_agent_orchestrator_execute_with_monitoring(tmp_path):
    """orchestrator.py: execute_with_monitoring with mocked RAGTool."""
    from src.orchestrator import AgentOrchestrator

    with patch("src.orchestrator.RAGTool") as MockRAG:
        mock_rag = MagicMock()
        mock_rag.retrieve.return_value = ["context line 1", "context line 2"]
        MockRAG.return_value = mock_rag

        orch = AgentOrchestrator(vector_db_url="mock://localhost")
        execution, evaluation = orch.execute_with_monitoring("analyse BTC")

    assert execution.completed is True
    assert "task_completion" in evaluation


def test_agent_orchestrator_prepare_context_empty_list(tmp_path):
    from src.orchestrator import AgentOrchestrator

    with patch("src.orchestrator.RAGTool") as MockRAG:
        mock_rag = MagicMock()
        mock_rag.retrieve.return_value = []  # empty list → _prepare_context returns None
        MockRAG.return_value = mock_rag

        orch = AgentOrchestrator(vector_db_url="mock://localhost")
        execution, _ = orch.execute_with_monitoring("task with no context")

    # SafeAgentBase.execute falls back to memory context when rag_context=None
    assert execution.completed is True


def test_agent_orchestrator_prepare_context_string(tmp_path):
    from src.orchestrator import AgentOrchestrator

    with patch("src.orchestrator.RAGTool") as MockRAG:
        mock_rag = MagicMock()
        mock_rag.retrieve.return_value = "direct string context"
        MockRAG.return_value = mock_rag

        orch = AgentOrchestrator(vector_db_url="mock://localhost")
        execution, _ = orch.execute_with_monitoring("another task")

    assert execution.context == "direct string context"


def test_agent_orchestrator_publish_agent_card(tmp_path):
    from src.orchestrator import AgentOrchestrator

    with patch("src.orchestrator.RAGTool") as MockRAG:
        MockRAG.return_value = MagicMock()
        orch = AgentOrchestrator(vector_db_url="mock://localhost")
        card = orch.publish_agent_card()

    assert "name" in card
    assert "skills" in card
