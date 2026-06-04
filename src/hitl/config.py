"""Operator-facing HITL autonomy configuration (levels 0-3).

Product decision (recorded): the dashboard/API expose **4 levels (0-3)** mirroring
the level *count* of :class:`src.hitl.progressive_autonomy.ProgressiveAutonomyManager`,
but with **USD auto-approval thresholds** as the operator-facing semantics. The
existing manager is trust-score driven; reconciling the two models (and expanding
to 0-5 with a real ``recovery_agent``) is deferred to Phase 3.

Counters in the snapshot are derived from real ``hitl_approval`` events in the
ledger — no fabricated numbers.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from src.core.ledger import TradingLedger


@dataclass(frozen=True)
class AutonomyLevel:
    """A single autonomy level the operator can select."""

    level: int
    threshold_usdt: float  # auto-approve orders up to this notional; 0 = none
    description: str


# Order matters: index == level.
AUTONOMY_LEVELS: Dict[int, AutonomyLevel] = {
    0: AutonomyLevel(0, 0.0, "Manual total — toda ordem exige aprovação humana"),
    1: AutonomyLevel(1, 500.0, "Semiautônomo baixo — aprova automático até $500 USDT"),
    2: AutonomyLevel(
        2, 1_000.0, "Semiautônomo médio — aprova automático até $1.000 USDT (padrão inicial)"
    ),
    3: AutonomyLevel(
        3,
        5_000.0,
        "Semiautônomo alto — aprova automático até $5.000 USDT, "
        "alertas críticos ainda requerem humano",
    ),
}

MIN_LEVEL = 0
MAX_LEVEL = 3
DEFAULT_LEVEL = 2


def level_info(level: int) -> AutonomyLevel:
    """Return the :class:`AutonomyLevel` for ``level`` (raises if out of range)."""
    if level not in AUTONOMY_LEVELS:
        raise ValueError(f"Autonomy level must be {MIN_LEVEL}-{MAX_LEVEL}, got {level}")
    return AUTONOMY_LEVELS[level]


def level_from_env() -> int:
    """Read ``AUTONOMY_LEVEL`` from the env, clamped to a valid level (default 2).

    Used by the loop process (which has no API HITLConfigStore) to size its
    auto-approval threshold from the deployment's configured autonomy level.
    """
    raw = os.getenv("AUTONOMY_LEVEL")
    if raw is None:
        return DEFAULT_LEVEL
    try:
        level = int(raw)
    except ValueError:
        return DEFAULT_LEVEL
    return level if MIN_LEVEL <= level <= MAX_LEVEL else DEFAULT_LEVEL



class HITLConfigStore:
    """Holds the current autonomy level and builds config snapshots.

    Persistence is in-memory for Phase 1 (seeded from ``initial_level``). Durable
    persistence (DB) is a Phase 2/3 concern; the API surface here will not change.
    """

    def __init__(self, ledger: TradingLedger, initial_level: int = DEFAULT_LEVEL) -> None:
        self._ledger = ledger
        self._level = level_info(initial_level).level
        self._last_changed_at: Optional[str] = None
        self._last_changed_by: Optional[str] = None
        # Optional override for the pending count (e.g. the real OrderStore).
        # When None, falls back to "open fills" as the closest truthful signal.
        self.pending_orders_provider: Optional[Callable[[], int]] = None

    @property
    def level(self) -> int:
        return self._level

    def set_level(self, level: int, reason: str, operator: str) -> "HITLConfigStore":
        """Change the autonomy level (validates range). ``reason`` is audited."""
        level_info(level)  # validate
        if not reason or len(reason.strip()) < 5:
            raise ValueError("A 'reason' of at least 5 characters is required")
        self._level = level
        self._last_changed_at = datetime.now(timezone.utc).isoformat()
        self._last_changed_by = operator
        self._ledger.log_decision(
            "hitl_level_changed",
            {"level": level, "reason": reason, "operator": operator},
        )
        return self

    def snapshot(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Build the current HITL config payload with real ledger-derived counters."""
        now = now or datetime.now(timezone.utc)
        today = now.date()
        info = AUTONOMY_LEVELS[self._level]

        approvals = self._ledger.get_events("hitl_approval")
        human_approved, human_rejected = self._count_today(approvals, today)

        pending = (
            self.pending_orders_provider()
            if self.pending_orders_provider is not None
            else self._pending_orders_count()
        )

        return {
            "current_level": self._level,
            "threshold_usdt": info.threshold_usdt,
            "level_description": info.description,
            "min_level": MIN_LEVEL,
            "max_level": MAX_LEVEL,
            "pending_orders_count": pending,
            "human_approved_today": human_approved,
            "human_rejected_today": human_rejected,
            "last_changed_at": self._last_changed_at,
            "last_changed_by": self._last_changed_by,
            "levels": [
                {
                    "level": lvl.level,
                    "threshold_usdt": lvl.threshold_usdt,
                    "description": lvl.description,
                }
                for lvl in AUTONOMY_LEVELS.values()
            ],
        }

    @staticmethod
    def _count_today(approvals: List[Dict[str, Any]], today: date) -> tuple[int, int]:
        approved = rejected = 0
        for entry in approvals:
            ts = entry.get("timestamp", "")
            try:
                when = datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
            except ValueError:
                continue
            if when != today:
                continue
            if entry.get("data", {}).get("approved"):
                approved += 1
            else:
                rejected += 1
        return approved, rejected

    def _pending_orders_count(self) -> int:
        """Open fills with no matching close = positions awaiting resolution.

        A real pending-order queue arrives in Phase 2 (HITL bridge); for now this
        reflects open positions, which is the closest truthful signal available.
        """
        closed_ids = {e["data"].get("order_id") for e in self._ledger.get_events("position_closed")}
        fills = self._ledger.get_events("order_fill")
        return sum(1 for f in fills if f["data"].get("order_id") not in closed_ids)


__all__ = [
    "AutonomyLevel",
    "AUTONOMY_LEVELS",
    "HITLConfigStore",
    "level_info",
    "MIN_LEVEL",
    "MAX_LEVEL",
    "DEFAULT_LEVEL",
]
