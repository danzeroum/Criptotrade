import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2]))

import asyncio

from src.agents.architect_agent import ArchitectAgent
from src.agents.developer_agent import DeveloperAgent
from src.agents.auditor_agent import AuditorAgent
from src.consensus.weighted_voting import WeightedConsensusEngine
from src.planning.adaptive_planner import AdaptivePlanner


def test_architect_cot_reasoning():
    architect = ArchitectAgent()
    task = {"description": "Design a microservices architecture for e-commerce", "priority": "high"}
    result = asyncio.run(architect.execute(task))
    assert result["success"] is True
    assert len(result["reasoning"]["reasoning_steps"]) == 5
    assert result["confidence"] >= 0.7


def test_developer_react_loop():
    developer = DeveloperAgent()
    task = {"description": "Implement REST API with CRUD operations"}
    result = asyncio.run(developer.execute(task))
    assert result["success"] is True
    assert result["history"], "history should not be empty"
    assert result["status"] in {"completed", "incomplete"}


def test_adaptive_planning():
    planner = AdaptivePlanner()
    task = {
        "task_id": "test-001",
        "description": "Complex task requiring adaptation",
        "priority": "high",
        "complexity": "high",
    }
    plan = asyncio.run(planner.create_adaptive_plan(task))
    assert plan["adaptive"] is True
    assert len(plan["steps"]) >= 3
    failed_step = plan["steps"][0]
    reflection = {"reason": "timeout", "details": "API timeout after 30s"}
    new_plan = asyncio.run(planner.replan_from_point(plan, failed_step, reflection))
    assert new_plan.get("replanned") is True
    assert len(new_plan["steps"]) >= len(plan["steps"]) + 1


def test_consensus_between_agents():
    engine = WeightedConsensusEngine()
    proposals = {
        "architect": {"confidence": 0.9, "proposal": {"solution": "microservices"}},
        "developer": {"confidence": 0.7, "proposal": {"solution": "monolith"}},
        "auditor": {"confidence": 0.8, "proposal": {"solution": "microservices"}},
    }
    result = engine.reach_consensus(proposals, "architecture")
    assert "decision" in result
    assert result["consensus_strength"] > 0
