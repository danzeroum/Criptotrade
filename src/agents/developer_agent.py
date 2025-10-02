"""Developer agent implementing the ReAct pattern."""
from __future__ import annotations

from typing import Any, Dict, List
import asyncio

from src.agents.base_agent import BaseAgent


class DeveloperAgent(BaseAgent):
    """Full-stack developer capable of a Thought → Action → Observation loop."""

    def __init__(self) -> None:
        super().__init__("developer")
        self.history: List[Dict[str, Any]] = []
        self.max_iterations = 5
        self.tools = [
            "write_code",
            "generate_tests",
            "refactor",
            "debug",
            "analyze_requirements",
        ]

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        if not self.validate_input(task):
            raise ValueError("Invalid development task payload")

        description = task.get("description", "")
        result = await self.react_loop(description)
        decision = {
            "task": task,
            "result": result,
            "iterations": len(self.history),
            "confidence": result.get("confidence", 0.0),
        }
        self.log_decision(decision)
        return {"success": True, "agent": self.agent_type, **result}

    async def react_loop(self, task: str) -> Dict[str, Any]:
        self.history.clear()
        for iteration in range(self.max_iterations):
            thought = await self.think(task)
            action = self.decide_action(thought)
            observation = await self.execute_action(action, task)
            self.history.append(
                {
                    "iteration": iteration,
                    "thought": thought,
                    "action": action,
                    "observation": observation,
                }
            )

            if self.is_task_complete(observation):
                return self.format_final_answer()
        return {"status": "incomplete", "history": self.history, "confidence": 0.4}

    async def think(self, task: str) -> str:
        await asyncio.sleep(0)
        if not self.history:
            return f"Understanding requirements for: {task}"
        last_observation = self.history[-1]["observation"]
        return f"Based on '{last_observation}', determine next best action"

    def decide_action(self, thought: str) -> Dict[str, Any]:
        lowered = thought.lower()
        if "understanding" in lowered:
            tool = "analyze_requirements"
        elif "test" in lowered:
            tool = "generate_tests"
        elif "refactor" in lowered:
            tool = "refactor"
        elif "debug" in lowered:
            tool = "debug"
        else:
            tool = "write_code"
        return {"tool": tool, "params": {}}

    async def execute_action(self, action: Dict[str, Any], task: str) -> str:
        await asyncio.sleep(0)
        tool = action.get("tool", "write_code")
        if tool == "analyze_requirements":
            return "Requirements analyzed: REST API with CRUD and auth"
        if tool == "generate_tests":
            return "Tests generated: pytest covering CRUD operations"
        if tool == "refactor":
            return "Refactor complete: reduced complexity"
        if tool == "debug":
            return "Debugging finished: no critical issues"
        return f"Code implemented for task '{task}'"

    def is_task_complete(self, observation: str) -> bool:
        lowered = observation.lower()
        return any(keyword in lowered for keyword in ["complete", "finished", "generated"])

    def format_final_answer(self) -> Dict[str, Any]:
        final_observation = self.history[-1]["observation"] if self.history else ""
        return {
            "status": "completed",
            "history": self.history,
            "final_output": final_observation,
            "confidence": 0.9,
        }
