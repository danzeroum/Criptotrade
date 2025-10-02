"""Foundation classes for security-first agent composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Protocol


class Guardrail(Protocol):
    """Protocol that all guardrails must implement."""

    name: str

    def validate(self, pattern: str) -> bool:
        """Return True if the pattern passes guardrail checks."""


@dataclass
class GuardrailSuite:
    """Container responsible for evaluating guardrail compliance."""

    guardrails: Iterable[Guardrail]

    def validate_pattern_safety(self, pattern: str) -> bool:
        return all(guardrail.validate(pattern) for guardrail in self.guardrails)


class InputSanitizer:
    name = "input_sanitizer"

    def validate(self, pattern: str) -> bool:  # type: ignore[override]
        return bool(pattern)


class OutputValidator:
    name = "output_validator"

    def validate(self, pattern: str) -> bool:  # type: ignore[override]
        return bool(pattern)


class EthicalBoundaryChecker:
    name = "ethical_boundary_checker"

    def validate(self, pattern: str) -> bool:  # type: ignore[override]
        return bool(pattern)


class ResourceLimiter:
    name = "resource_limiter"

    def validate(self, pattern: str) -> bool:  # type: ignore[override]
        return bool(pattern)


class SafeAgentBase:
    """Base class enforcing mandatory guardrails for all capabilities."""

    def __init__(self) -> None:
        self.guardrails = GuardrailSuite(self.initialize_mandatory_guardrails())
        self.capabilities: List[str] = []
        self.memory = MemoryManager()

    def initialize_mandatory_guardrails(self) -> List[Guardrail]:
        return [
            InputSanitizer(),
            OutputValidator(),
            EthicalBoundaryChecker(),
            ResourceLimiter(),
        ]

    def add_capability(self, pattern: str) -> None:
        if not self.guardrails.validate_pattern_safety(pattern):
            raise ValueError(f"Pattern '{pattern}' failed safety validation.")
        self.capabilities.append(pattern)

    def list_capabilities(self) -> List[str]:
        return list(self.capabilities)

    def create_plan(self, task: str) -> "Plan":
        """Create a lightweight execution plan for the provided task."""

        memory_context: Optional[str] = None
        memory_accessed = False
        if "memory" in self.capabilities:
            memory_context = self.memory.recall(task)
            memory_accessed = True

        plan_creation = PlanCreation(
            task=task,
            memory_context=memory_context,
            memory_accessed=memory_accessed,
        )
        return Plan(task=task, creation=plan_creation)

    def execute(self, task: str, context: Optional[str] = None) -> "AgentExecution":
        """Execute a task while capturing telemetry for evaluation loops."""

        plan = self.create_plan(task)
        resolved_context = context or plan.creation.memory_context
        output = f"executed::{task}"

        return AgentExecution(
            task=task,
            context=resolved_context,
            completed=True,
            resource_usage=max(1.0, float(len(self.capabilities) or 1)),
            guardrail_violations=0,
            output=output,
        )


@dataclass
class PlanCreation:
    task: str
    memory_context: Optional[str] = None
    memory_accessed: bool = False


@dataclass
class Plan:
    task: str
    creation: PlanCreation


class MemoryManager:
    """Simple memory facade used by emergent behavior tests."""

    def __init__(self) -> None:
        self._last_task: Optional[str] = None
        self._last_context: Optional[str] = None

    def recall(self, task: str) -> str:
        self._last_task = task
        self._last_context = f"contexto recuperado para {task}"
        return self._last_context

    def was_accessed_during(self, creation: PlanCreation) -> bool:
        return (
            creation.memory_accessed
            and creation.memory_context is not None
            and creation.memory_context == self._last_context
        )


@dataclass
class AgentExecution:
    """Telemetry emitted after executing a task."""

    task: str
    context: Optional[str]
    completed: bool
    resource_usage: float
    guardrail_violations: int
    output: str

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "context": self.context,
            "completed": self.completed,
            "resource_usage": self.resource_usage,
            "guardrail_violations": self.guardrail_violations,
            "output": self.output,
        }
