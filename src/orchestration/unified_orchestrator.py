"""Unified orchestrator integrating advanced agent patterns."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from src.agents.architect_agent import ArchitectAgent
from src.agents.auditor_agent import AuditorAgent
from src.agents.developer_agent import DeveloperAgent
from src.agents.designer_agent import DesignerAgent
from src.agents.ops_agent import OpsAgent
from src.chains.resilient_chain import ResilientPromptChain
from src.consensus.weighted_voting import WeightedConsensusEngine
from src.evaluation.continuous_evaluator import ContinuousEvaluator
from src.hitl.progressive_autonomy import ProgressiveAutonomyManager
from src.memory.agent_memory import AgentMemorySystem
from src.parallel.resource_manager import ParallelResourceManager
from src.planning.adaptive_planner import AdaptivePlanner
from src.routing.learning_router import LearningRouter
from src.tools.sandbox.secure_executor import SecureToolSandbox

logger = logging.getLogger(__name__)


class UnifiedOrchestrator:
    """High level orchestrator bridging all subsystems."""

    def __init__(self) -> None:
        self.planner = AdaptivePlanner()
        self.router = LearningRouter()
        self.parallel = ParallelResourceManager()
        self.memory = AgentMemorySystem()
        self.evaluator = ContinuousEvaluator()
        self.consensus = WeightedConsensusEngine()
        self.autonomy = ProgressiveAutonomyManager()
        self.sandbox = SecureToolSandbox()
        self.chain_manager = ResilientPromptChain([])

        self.agents: Dict[str, Any] = {
            "architect": ArchitectAgent(),
            "developer": DeveloperAgent(),
            "auditor": AuditorAgent(),
            "designer": DesignerAgent(),
            "ops": OpsAgent(),
        }
        for agent in self.agents.values():
            agent.attach_memory(self.memory)

    async def execute_complex_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task.get("task_id", str(uuid.uuid4()))
        start = datetime.now(timezone.utc)
        logger.info("Starting execution for task %s", task_id)

        relevant_context = self.memory.recall_similar(task.get("description", ""), k=5)
        plan = await self.planner.create_adaptive_plan(task)
        proposals = await self._get_squad_proposals(plan)
        consensus = self.consensus.reach_consensus(proposals, "architecture")

        if consensus.get("consensus_strength", 0.0) < 0.7:
            approval = await self.autonomy.execute_with_autonomy(
                "orchestrator",
                {"action": "approve_plan", "plan": plan, "critical": True},
            )
            if not approval.get("executed", False):
                return {
                    "success": False,
                    "task_id": task_id,
                    "reason": "Plan rejected",
                    "consensus": consensus,
                }

        execution_results = await self._execute_plan_steps(plan, task)
        final_validation = await self.agents["auditor"].validate_results(execution_results)

        self.memory.remember_decision(
            "orchestrator",
            {
                "task_id": task_id,
                "task": task,
                "plan": plan,
                "results": execution_results,
                "validation": final_validation,
                "context_recall": relevant_context,
                "duration_seconds": (datetime.now(timezone.utc) - start).total_seconds(),
            },
        )

        await self._update_learning(task, execution_results)

        return {
            "success": final_validation.get("approved", False),
            "task_id": task_id,
            "plan": plan,
            "consensus": consensus,
            "results": execution_results,
            "validation": final_validation,
            "confidence": final_validation.get("confidence", 0.0),
        }

    async def _get_squad_proposals(self, plan: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        proposals: Dict[str, Dict[str, Any]] = {}

        architect_result = await self.agents["architect"].execute(
            {"description": f"Review plan: {plan['goal']}", "plan": plan}
        )
        proposals["architect"] = {
            "confidence": architect_result.get("confidence", 0.5),
            "proposal": architect_result,
        }

        developer_result = await self.agents["developer"].execute(
            {"description": f"Assess implementation for {plan['goal']}", "plan": plan}
        )
        proposals["developer"] = {
            "confidence": developer_result.get("confidence", 0.5),
            "proposal": developer_result,
        }

        audit_result = await self.agents["auditor"].execute(
            {
                "description": f"Audit plan {plan['goal']}",
                "plan": plan,
                "metrics": {"complexity": len(plan["steps"]), "coverage": 85},
            }
        )
        proposals["auditor"] = {
            "confidence": audit_result.get("confidence", 0.5),
            "proposal": audit_result,
        }

        return proposals

    async def _execute_plan_steps(self, plan: Dict[str, Any], task: Dict[str, Any]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for step in plan["steps"]:
            agent_name = self._select_agent_for_step(step)
            if self._can_parallelize(step, plan):
                parallel_tasks = self._extract_parallel_tasks(step)
                step_results = await self.parallel.execute_parallel_with_limits(parallel_tasks)
                for result in step_results:
                    await self.evaluator.evaluate_agent_performance(agent_name, result)
                results.extend(step_results)
                continue

            step_task = {"description": step["description"], "action": step["action"], "step": step["step"]}
            result = await self.agents[agent_name].execute(step_task)
            quality = await self.evaluator.evaluate_agent_performance(agent_name, result)
            if quality.get("technical_score", 0) < 0.6:
                reflection = {"reason": "low_quality", "score": quality.get("technical_score", 0)}
                plan = await self.planner.replan_from_point(plan, step, reflection)
            results.append(result)
        return results

    def _select_agent_for_step(self, step: Dict[str, Any]) -> str:
        mapping = {
            "analyze": "architect",
            "design": "designer",
            "implement": "developer",
            "validate": "auditor",
            "deploy": "ops",
        }
        return mapping.get(step.get("action", ""), "developer")

    def _can_parallelize(self, step: Dict[str, Any], plan: Dict[str, Any]) -> bool:
        if step.get("dependencies"):
            return False
        if step.get("action") in {"validate", "deploy"}:
            return False
        return True

    def _extract_parallel_tasks(self, step: Dict[str, Any]) -> Iterable:
        description = step.get("description", "")

        async def developer_task() -> Dict[str, Any]:
            return await self.agents["developer"].execute({"description": f"Parallel dev: {description}"})

        async def designer_task() -> Dict[str, Any]:
            return await self.agents["designer"].execute({"description": f"Parallel design: {description}"})

        return [developer_task, designer_task]

    async def _update_learning(self, task: Dict[str, Any], results: List[Dict[str, Any]]) -> None:
        for result in results:
            route = result.get("route", "default")
            success = result.get("success", False)
            latency = result.get("duration", 0.0)
            self.router.update_route_performance(task, route, success, float(latency))

    async def _attempt_recovery(self, task: Dict[str, Any], error: str) -> Optional[Dict[str, Any]]:
        simplified_task = {"description": task.get("description", ""), "priority": "low", "simplified": True}
        try:
            return await self.execute_complex_task(simplified_task)
        except Exception:  # pragma: no cover - defensive
            logger.exception("Recovery failed for task: %s", task.get("description"))
            return None
