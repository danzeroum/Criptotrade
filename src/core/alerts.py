"""Alert bus + persistence for guardrail / risk events.

Why in-process (not Redis): per the architecture decision, this is a
single-operator, single-process system in its validation phase. An in-process
``asyncio`` broadcaster is simpler and sufficient; swapping in Redis Streams is a
future scaling decision behind the same ``publish_alert`` surface.

Two responsibilities, deliberately separated:
* :class:`AlertStore` — durable history (append-only JSONL), filter/read.
* :class:`AlertBus` — live fan-out to SSE subscribers in the same process.

``publish_alert`` does both: persist, then broadcast best-effort.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SEVERITIES = ("low", "medium", "high", "critical")


@dataclass
class Alert:
    """A guardrail/risk alert."""

    severity: str
    type: str
    message: str
    agent_id: Optional[str] = None
    pair: Optional[str] = None
    auto_action: Optional[str] = None
    id: str = field(default_factory=lambda: "alert_" + uuid.uuid4().hex[:8])
    occurred_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"severity must be one of {SEVERITIES}, got {self.severity!r}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AlertStore:
    """Append-only JSONL persistence for alerts."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(".buildtovalue/ledger/alerts.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, alert: Alert) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(alert.to_dict(), ensure_ascii=False) + "\n")

    def history(
        self,
        severity: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """Return ``(alerts, total)`` newest-first, optionally filtered."""
        if not self.path.exists():
            return [], 0

        rows: List[Dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if severity and row.get("severity") != severity:
                    continue
                if since is not None:
                    ts = _parse_ts(row.get("occurred_at"))
                    if ts is None or ts < since:
                        continue
                rows.append(row)

        rows.reverse()  # newest first
        total = len(rows)
        return rows[offset : offset + limit], total


class AlertBus:
    """In-process async fan-out to live subscribers (e.g. SSE connections).

    Subscribers register an :class:`asyncio.Queue` and drain it themselves, which
    keeps the consumer in control of timeouts/heartbeats and avoids fragile
    async-generator delegation.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[Dict[str, Any]]] = set()

    async def publish(self, alert: Alert) -> None:
        payload = alert.to_dict()
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:  # pragma: no cover - slow consumer guard
                logger.warning("Dropping alert for slow subscriber")

    def register(self) -> "asyncio.Queue[Dict[str, Any]]":
        """Register a new subscriber queue."""
        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        return queue

    def unregister(self, queue: "asyncio.Queue[Dict[str, Any]]") -> None:
        self._subscribers.discard(queue)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def publish_alert(alert: Alert, store: AlertStore, bus: AlertBus) -> Alert:
    """Persist ``alert`` to ``store`` then broadcast on ``bus`` (best-effort)."""
    store.append(alert)
    await bus.publish(alert)
    return alert


__all__ = ["Alert", "AlertStore", "AlertBus", "publish_alert", "SEVERITIES"]
