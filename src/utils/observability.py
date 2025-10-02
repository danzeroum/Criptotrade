"""Observability primitives for tracking agent decisions and actions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


def generate_trace_id() -> str:
    """Return a globally unique identifier for observability spans."""
    return uuid.uuid4().hex


@dataclass
class SpanRecord:
    """Structured record of a single agent operation."""

    operation: str
    metadata: Dict[str, Any]
    start_time: datetime = field(default_factory=datetime.utcnow)
    reasoning_log: List[str] = field(default_factory=list)
    end_time: Optional[datetime] = None

    def log_reasoning(self, thought_process: str) -> None:
        """Append a reasoning message to the span."""
        self.reasoning_log.append(thought_process)

    def close(self) -> None:
        """Mark the span as completed."""
        self.end_time = datetime.utcnow()


class AgentObserver:
    """Simple tracing facility for orchestrated agent workflows."""

    def __init__(self) -> None:
        self.trace_id: str = generate_trace_id()
        self.spans: List[SpanRecord] = []

    def start_span(self, operation: str, metadata: Optional[Dict[str, Any]] = None) -> SpanRecord:
        """Create a new span and register it with the observer."""
        record = SpanRecord(operation=operation, metadata=metadata or {})
        self.spans.append(record)
        return record

    def log_reasoning(self, thought_process: str) -> None:
        """Log reasoning to the most recent span for quick introspection."""
        if not self.spans:
            raise RuntimeError("No active span to record reasoning against.")
        self.spans[-1].log_reasoning(thought_process)

    def export_trajectory(self) -> Dict[str, Any]:
        """Export a serializable representation of the agent trajectory."""
        return {
            "trace_id": self.trace_id,
            "spans": [
                {
                    "operation": span.operation,
                    "metadata": span.metadata,
                    "start_time": span.start_time.isoformat() + "Z",
                    "end_time": span.end_time.isoformat() + "Z" if span.end_time else None,
                    "reasoning_log": span.reasoning_log,
                }
                for span in self.spans
            ],
        }
