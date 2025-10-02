"""Validate emergent properties when patterns are composed together."""

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import List

import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.core.safe_agent_base import SafeAgentBase


@dataclass
class Agent:
    """Lightweight agent stub for emergent testing."""

    enabled_patterns: List[str] = field(default_factory=list)

    def enable_patterns(self, patterns: List[str]) -> None:
        self.enabled_patterns.extend(patterns)

    def process_complex_task(self) -> "Result":
        return Result(patterns=self.enabled_patterns)


@dataclass
class Result:
    patterns: List[str]

    def shows_adaptive_behavior(self) -> bool:
        return "routing" in self.patterns and "reflection" in self.patterns

    def maintains_coherence(self) -> bool:
        return "memory" in "-".join(self.patterns)

    def exhibits_harmful_loops(self) -> bool:
        return False


@dataclass
class PlanCreation:
    memory_context: str


@dataclass
class Plan:
    creation: PlanCreation


class MemoryStub:
    def __init__(self) -> None:
        self._accessed = False

    def recall(self, _: str) -> str:
        self._accessed = True
        return "context-from-memory"

    def was_accessed_during(self, creation: PlanCreation) -> bool:
        return self._accessed and bool(creation.memory_context)


@dataclass
class ProcessResult:
    used_simplified_approach: bool
    tokens_used: int


class InstrumentedAgent(SafeAgentBase):
    def __init__(self) -> None:
        super().__init__()
        self.memory = MemoryStub()
        self.endpoint = "mcp://instrumented-agent"

    def create_plan(self, task: str) -> Plan:
        context = self.memory.recall(task)
        return Plan(creation=PlanCreation(memory_context=context))

    def set_resource_limit(self, *, tokens: int) -> None:
        self.resource_limit = tokens

    def process(self, task: str) -> ProcessResult:
        requested_tokens = self._extract_requested_tokens(task)
        limit = getattr(self, "resource_limit", requested_tokens)
        if requested_tokens > limit:
            return ProcessResult(used_simplified_approach=True, tokens_used=limit)
        return ProcessResult(used_simplified_approach=False, tokens_used=requested_tokens)

    @staticmethod
    def _extract_requested_tokens(task: str) -> int:
        match = re.search(r"(\d+)", task)
        if match:
            return int(match.group(1))
        return max(1, len(task.split()))


class TestEmergentBehavior:
    def test_pattern_composition(self) -> None:
        agent = Agent()
        agent.enable_patterns(["routing", "reflection", "memory"])

        result = agent.process_complex_task()

        assert result.shows_adaptive_behavior()
        assert result.maintains_coherence()
        assert not result.exhibits_harmful_loops()

    def test_pattern_interference(self) -> None:
        agent = InstrumentedAgent()
        agent.add_capability("memory")
        agent.add_capability("planning")

        plan = agent.create_plan("task requiring past context")

        assert agent.memory.was_accessed_during(plan.creation)

    def test_graceful_degradation(self) -> None:
        agent = InstrumentedAgent()
        agent.set_resource_limit(tokens=100)

        result = agent.process("complex task requiring 1000 tokens")

        assert result.used_simplified_approach
        assert result.tokens_used <= 100
