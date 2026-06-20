"""Orchestrator loop heartbeat — operability / restart & liveness detection.

The loop has no HTTP endpoint, so it writes a small heartbeat file each cycle.
``scripts/healthcheck_loop.py`` reads it for the docker-compose healthcheck.
Everything is best-effort: a heartbeat error must never break a trading cycle.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

HEARTBEAT_FILENAME = "loop_heartbeat.json"


def write_heartbeat(path: Path | str, cycle_id: str) -> None:
    """Write ``{ts, cycle_id}`` to ``path`` (best-effort)."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps({"ts": time.time(), "cycle_id": cycle_id}), encoding="utf-8"
        )
    except Exception:  # pragma: no cover - best effort, never break the loop
        logger.warning("Could not write loop heartbeat", exc_info=True)


def read_heartbeat(path: Path | str) -> Optional[dict[str, Any]]:
    """Return the parsed heartbeat, or None if missing/unreadable."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def is_fresh(
    hb: Optional[dict[str, Any]], max_age_seconds: float, now: Optional[float] = None
) -> bool:
    """True if ``hb`` exists and its timestamp is within ``max_age_seconds``."""
    if not hb or "ts" not in hb:
        return False
    current = time.time() if now is None else now
    try:
        return (current - float(hb["ts"])) <= max_age_seconds
    except (TypeError, ValueError):
        return False


__all__ = ["write_heartbeat", "read_heartbeat", "is_fresh", "HEARTBEAT_FILENAME"]
