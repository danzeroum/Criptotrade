import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2]))

import asyncio

from src.orchestration.unified_orchestrator import UnifiedOrchestrator


def test_orchestrator_simple_task():
    orchestrator = UnifiedOrchestrator()
    task = {
        "task_id": "test-001",
        "description": "Create a simple REST API",
        "priority": "medium",
        "requirements": ["FastAPI", "PostgreSQL", "Docker"],
    }
    result = asyncio.run(orchestrator.execute_complex_task(task))
    assert result["success"] is True
    assert result["task_id"] == "test-001"
    assert result["confidence"] >= 0.0


def test_orchestrator_with_replanning():
    orchestrator = UnifiedOrchestrator()
    task = {
        "task_id": "test-002",
        "description": "Complex task with potential failure",
        "priority": "high",
        "simulate_failure": True,
    }
    result = asyncio.run(orchestrator.execute_complex_task(task))
    assert "plan" in result
    assert result["plan"].get("adaptive") is True


def test_consensus_mechanism():
    orchestrator = UnifiedOrchestrator()
    task = {
        "task_id": "test-003",
        "description": "Architectural decision requiring consensus",
        "priority": "critical",
        "requires_consensus": True,
    }
    result = asyncio.run(orchestrator.execute_complex_task(task))
    assert "consensus" in result
    assert result["consensus"]["consensus_strength"] >= 0.0
