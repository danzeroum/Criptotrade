"""Common base class providing shared utilities for BuildToValue agents."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import logging
import uuid

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base behaviour shared by the specialised agents."""

    def __init__(self, agent_type: str) -> None:
        self.agent_type = agent_type
        self.agent_id = str(uuid.uuid4())
        self.created_at = datetime.now(timezone.utc)
        self.confidence_threshold = 0.7
        self.memory = None  # injected lazily by orchestrators
        self.tools: list[str] = []

    @abstractmethod
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the primary responsibility for the agent."""

    def validate_input(self, task: Dict[str, Any]) -> bool:
        """Basic validation hook to guarantee required metadata exists."""

        return "description" in task and bool(task["description"])

    def log_decision(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Persist the decision to memory and log the action."""

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": self.agent_type,
            "agent_id": self.agent_id,
            "decision": decision,
        }

        if self.memory:
            try:
                self.memory.remember_decision(self.agent_type, entry)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("Unable to persist agent memory", exc_info=exc)

        logger.info("%s recorded decision", self.agent_type, extra={"decision": entry})
        return entry

    def attach_memory(self, memory: Any) -> None:
        """Allow orchestrators to inject a memory backend."""

        self.memory = memory

    def validate_confidence(self, confidence: Optional[float]) -> bool:
        """Convenience helper for subclasses when evaluating responses."""

        if confidence is None:
            return False
        return confidence >= self.confidence_threshold
