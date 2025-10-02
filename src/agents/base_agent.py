"""Base agent class for crypto trading system."""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import logging
import uuid

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all trading agents."""

    def __init__(self, agent_type: str) -> None:
        self.agent_type = agent_type
        self.agent_id = str(uuid.uuid4())
        self.created_at = datetime.now(timezone.utc)
        self.confidence_threshold = 0.6
        self.memory = None
        self.tools: list[str] = []

    @abstractmethod
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's primary responsibility."""
        pass

    def validate_input(self, task: Dict[str, Any]) -> bool:
        """Validate task input."""
        return bool(task)

    def log_decision(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Log decision to memory and audit trail."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": self.agent_type,
            "agent_id": self.agent_id,
            "decision": decision,
        }

        if self.memory:
            try:
                self.memory.remember_decision(self.agent_type, entry)
            except Exception as exc:
                logger.warning("Unable to persist agent memory", exc_info=exc)

        logger.info(f"{self.agent_type} recorded decision", extra={"decision": entry})
        return entry

    def attach_memory(self, memory: Any) -> None:
        """Attach memory backend."""
        self.memory = memory

    def validate_confidence(self, confidence: Optional[float]) -> bool:
        """Check if confidence meets threshold."""
        if confidence is None:
            return False
        return confidence >= self.confidence_threshold
