"""Architect agent implementing Chain-of-Thought reasoning."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
import logging

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ArchitectAgent(BaseAgent):
    """Senior system architect capable of Chain-of-Thought analysis."""

    def __init__(self) -> None:
        super().__init__("architect")
        self.reasoning_history: List[Dict[str, Any]] = []
        self.tools = ["analyze_architecture", "generate_adr"]

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        if not self.validate_input(task):
            raise ValueError("Invalid architectural task payload")

        description = task.get("description", "")
        reasoning = self.reason_with_cot(description)
        plan = await self.create_plan(task, reasoning)
        adr = self.create_adr({
            "title": task.get("title", description[:60] or "Architecture Decision"),
            "problem_analysis": reasoning.get("problem_analysis", description),
            "recommendation": reasoning.get("recommendation", plan.get("architecture")),
            "trade_offs": reasoning.get("trade_offs", {}),
        })

        decision = {
            "task": task,
            "reasoning": reasoning,
            "plan": plan,
            "adr": adr,
            "confidence": reasoning.get("confidence", 0.0),
        }
        self.log_decision(decision)

        return {
            "success": True,
            "agent": self.agent_type,
            "reasoning": reasoning,
            "plan": plan,
            "adr": adr,
            "confidence": reasoning.get("confidence", 0.0),
        }

    def reason_with_cot(self, problem: str) -> Dict[str, Any]:
        """Produce a detailed, step-by-step architectural reasoning chain."""

        steps = [
            {
                "step": 1,
                "prompt": "Identify the core problem",
                "result": problem.strip() or "Problema não especificado",
            },
            {
                "step": 2,
                "prompt": "List the technical constraints",
                "result": ["P95 < 800ms", "Escalabilidade", "Compatibilidade retroativa"],
            },
            {
                "step": 3,
                "prompt": "Evaluate applicable design patterns",
                "result": ["Repository", "Factory", "Observer"],
            },
            {
                "step": 4,
                "prompt": "Analyse trade-offs",
                "result": {
                    "Repository": "Simplifica persistência mas adiciona camada extra",
                    "Observer": "Permite reatividade porém aumenta complexidade",
                },
            },
            {
                "step": 5,
                "prompt": "Select the optimal solution",
                "result": "Utilizar micro-serviços com camada de API Gateway e cache",
            },
        ]

        response = {
            "problem_analysis": steps[0]["result"],
            "constraints": steps[1]["result"],
            "applicable_patterns": steps[2]["result"],
            "trade_offs": steps[3]["result"],
            "recommendation": steps[4]["result"],
            "confidence": 0.85,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reasoning_steps": steps,
        }
        self.reasoning_history.append(response)
        return response

    async def create_plan(self, task: Dict[str, Any], reasoning: Dict[str, Any]) -> Dict[str, Any]:
        """Derive a lightweight architectural plan informed by the reasoning."""

        components = [
            "API Gateway",
            "Auth Service",
            "Business Logic",
            "Database",
        ]
        if "cache" in reasoning.get("recommendation", "").lower():
            components.append("Caching Layer")

        return {
            "goal": task.get("description", ""),
            "architecture": "microservices",
            "components": components,
            "patterns": reasoning.get("applicable_patterns", []),
            "risks": ["Complexidade", "Custo operacional"],
            "mitigations": ["Documentação", "Observabilidade"],
            "estimated_effort": "2 sprints",
        }

    def create_adr(self, decision: Dict[str, Any]) -> str:
        """Generate an Architecture Decision Record style note."""

        return (
            f"# ADR: {decision.get('title', 'Architecture Decision')}\n\n"
            "## Status\nAccepted\n\n"
            "## Context\n"
            f"{decision.get('problem_analysis', 'N/A')}\n\n"
            "## Decision\n"
            f"{decision.get('recommendation', 'N/A')}\n\n"
            "## Consequences\n"
            f"{decision.get('trade_offs', 'N/A')}\n"
        )
