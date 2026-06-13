"""Tests for MCPToolRegistry."""
from __future__ import annotations

import pytest

from src.tools.mcp_registry import MCPToolRegistry


def test_registry_registers_core_tools_on_init():
    reg = MCPToolRegistry()
    assert "analyze_code_quality" in reg.tools
    assert "generate_tests" in reg.tools
    assert "optimize_performance" in reg.tools


def test_analyze_code_quality_returns_expected_shape():
    reg = MCPToolRegistry()
    result = reg.execute("analyze_code_quality", "src/core/ledger.py")
    assert result["file"] == "src/core/ledger.py"
    assert "complexity" in result
    assert "coverage" in result
    assert isinstance(result["issues"], list)


def test_generate_tests_includes_framework_in_output():
    reg = MCPToolRegistry()
    result = reg.execute("generate_tests", "def foo(): pass", framework="pytest")
    assert "pytest" in result


def test_generate_tests_default_framework():
    reg = MCPToolRegistry()
    result = reg.execute("generate_tests", "x = 1")
    assert "pytest" in result  # default framework


def test_optimize_performance_returns_suggestions():
    reg = MCPToolRegistry()
    result = reg.execute("optimize_performance", "for i in range(10): pass")
    assert "suggestions" in result
    assert "estimated_gain" in result


def test_execute_unknown_tool_raises_key_error():
    reg = MCPToolRegistry()
    with pytest.raises(KeyError, match="registrada"):
        reg.execute("nonexistent_tool")


def test_register_tool_decorator_adds_to_registry():
    reg = MCPToolRegistry()

    @reg.register_tool("custom_tool")
    def my_tool(x: int) -> int:
        return x * 2

    assert "custom_tool" in reg.tools
    assert reg.execute("custom_tool", 5) == 10


def test_empty_tools_dict_triggers_register_core():
    reg = MCPToolRegistry(tools={})
    # __post_init__ should have registered core tools
    assert len(reg.tools) >= 3


def test_prepopulated_tools_skips_core_registration():
    def _dummy(x):
        return x

    reg = MCPToolRegistry(tools={"my_tool": _dummy})
    # __post_init__ should NOT call register_core_tools (tools not empty)
    # core tools should NOT be present
    assert "analyze_code_quality" not in reg.tools
    assert "my_tool" in reg.tools
