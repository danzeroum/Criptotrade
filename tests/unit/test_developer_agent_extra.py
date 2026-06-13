"""Extra coverage for DeveloperAgent — branch paths in decide_action and execute_action."""
from __future__ import annotations

import pytest

from src.agents.developer_agent import DeveloperAgent


@pytest.mark.asyncio
async def test_execute_invalid_task_raises():
    """Line 27: validate_input fails → ValueError raised."""
    agent = DeveloperAgent()
    with pytest.raises(ValueError, match="Invalid development task payload"):
        await agent.execute(None)


def test_decide_action_refactor():
    """Line 73: 'refactor' in thought → tool=refactor."""
    agent = DeveloperAgent()
    result = agent.decide_action("We should refactor this module")
    assert result["tool"] == "refactor"


def test_decide_action_debug():
    """Line 75: 'debug' in thought → tool=debug."""
    agent = DeveloperAgent()
    result = agent.decide_action("Need to debug the authentication issue")
    assert result["tool"] == "debug"


@pytest.mark.asyncio
async def test_execute_action_generate_tests():
    """Line 88: tool=generate_tests → returns test generation response."""
    agent = DeveloperAgent()
    result = await agent.execute_action({"tool": "generate_tests"}, "some task")
    assert "Tests generated" in result


@pytest.mark.asyncio
async def test_execute_action_refactor():
    """Line 90: tool=refactor → returns refactor completion response."""
    agent = DeveloperAgent()
    result = await agent.execute_action({"tool": "refactor"}, "some task")
    assert "Refactor complete" in result


def test_decide_action_understanding():
    """'understanding' in thought → tool=analyze_requirements."""
    agent = DeveloperAgent()
    result = agent.decide_action("Understanding the requirements for this feature")
    assert result["tool"] == "analyze_requirements"


def test_decide_action_test():
    """'test' in thought → tool=generate_tests."""
    agent = DeveloperAgent()
    result = agent.decide_action("Write tests for this function")
    assert result["tool"] == "generate_tests"
