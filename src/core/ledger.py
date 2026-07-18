"""Immutable audit ledger for all trading decisions (SQLite/WAL — ADR-003).

Writes funnel through :meth:`log_decision`; reads (:meth:`read_all`,
:meth:`get_events`, :meth:`get_process_events`, :meth:`get_recent_trades`)
preserve the historical ``{"timestamp", "event_type", "data"}`` entry shape, so
callers are unaffected by the JSONL→SQLite migration. ``event_type`` is indexed,
so ``get_events`` no longer scans the whole log.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.core.db import autoincrement_pk, connection

logger = logging.getLogger(__name__)


def _ledger_dir() -> Path:
    """Base dir for runtime ledger files.

    Honours ``LEDGER_DIR`` so deployments can point it at a mounted volume
    (e.g. ``/app/data/ledger`` in docker-compose) and survive container restarts.
    Defaults to the repo-local path for development.
    """
    return Path(os.getenv("LEDGER_DIR", ".buildtovalue/ledger"))


class TradingLedger:
    """Append-only audit trail, backed by SQLite (WAL) for indexed reads."""

    def __init__(self, ledger_path: Path | None = None) -> None:
        # ``ledger_path`` keeps its historical meaning/name (the legacy JSONL
        # location); events now live in a sibling SQLite db so the two loop
        # processes share them with WAL concurrency. A legacy trades.jsonl can be
        # imported once with scripts/migrate_ledger.py.
        self.ledger_path = ledger_path or _ledger_dir() / "trades.jsonl"
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = self.ledger_path.with_suffix(".db")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with connection(self.db_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS ledger_events ("
                f"  id {autoincrement_pk()},"
                "  timestamp TEXT NOT NULL,"
                "  event_type TEXT NOT NULL,"
                "  data TEXT NOT NULL"  # JSON payload
                ")"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ledger_events_type ON ledger_events(event_type)"
            )

    def log_decision(
        self, event_type: str, data: Dict[str, Any], timestamp: str | None = None
    ) -> None:
        """Append a trading decision/event. ``timestamp`` defaults to now (UTC);
        pass an explicit ISO value to preserve a historical event's time (used by
        the migration script and time-sensitive tests)."""
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        with connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO ledger_events(timestamp, event_type, data) VALUES (?, ?, ?)",
                (ts, event_type, json.dumps(data, ensure_ascii=False)),
            )
        logger.info("Ledger entry recorded", extra={"event_type": event_type})

    def log_signal(self, agent: str, signal: Dict[str, Any]) -> None:
        """Log a trading signal."""
        self.log_decision("signal_generated", {"agent": agent, "signal": signal})

    def log_validation(self, agent: str, validation: Dict[str, Any]) -> None:
        """Log a risk validation."""
        self.log_decision("risk_validation", {"agent": agent, "validation": validation})

    def log_execution(self, agent: str, execution: Dict[str, Any]) -> None:
        """Log an order execution."""
        self.log_decision("order_executed", {"agent": agent, "execution": execution})

    def log_hitl_approval(self, approved: bool, order: Dict[str, Any], user: str = "default") -> None:
        """Log human-in-the-loop approval decision."""
        self.log_decision("hitl_approval", {"approved": approved, "order": order, "user": user})

    def log_auth_event(
        self,
        event: str,
        *,
        actor: str,
        email: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
        success: bool = True,
        detail: str | None = None,
    ) -> None:
        """Append an authentication/security event (A1; the A4 audit-trail feed).

        Event types are ``auth_<event>`` (login, logout, 2fa_enabled,
        password_reset, session_refresh_reuse, ...). Names are STABLE — the A4
        audit screen will filter on them; carry actor + IP + user-agent so the
        audit detail view works with no schema change.
        """
        self.log_decision(
            f"auth_{event}",
            {
                "actor": actor, "email": email, "ip": ip,
                "user_agent": user_agent, "success": success, "detail": detail,
            },
        )

    def log_process_event(
        self,
        case_id: str,
        activity: str,
        actor: str,
        attributes: Dict[str, Any] | None = None,
    ) -> None:
        """Append an XES-style process event for process mining.

        Maps to the classic XES triple: ``case_id`` (the trace, e.g. an order id),
        ``activity`` (the step, e.g. ``order_filled``) and ``actor`` (resource that
        performed it). ``attributes`` carries any extra payload. These events are
        the event log a tool like PM4Py consumes to discover the real process.
        """
        self.log_decision(
            "process_event",
            {"case_id": case_id, "activity": activity, "actor": actor, "attributes": attributes or {}},
        )

    def get_process_events(self, case_id: str | None = None) -> List[Dict[str, Any]]:
        """Return process events (XES log), optionally filtered by ``case_id``."""
        events = self.get_events("process_event")
        if case_id is None:
            return events
        return [e for e in events if e["data"].get("case_id") == case_id]

    def log_fill(
        self,
        order_id: str,
        symbol: str,
        side: str,
        price: float,
        quantity: float,
        fee: float = 0.0,
        strategy: str | None = None,
        agent: str = "execution",
    ) -> None:
        """Log an order fill with the structured fields needed to value positions.

        Unlike :meth:`log_execution` (which records the agent's raw result), this
        captures the *economic* facts of the fill (price, quantity, fee) so the
        metrics engine can compute exposure, open positions and realised P&L.
        """
        notional = price * quantity
        self.log_decision(
            "order_fill",
            {
                "order_id": order_id,
                "symbol": symbol,
                "side": side.lower(),
                "price": price,
                "quantity": quantity,
                "notional": notional,
                "fee": fee,
                "strategy": strategy,
                "agent": agent,
            },
        )

    def log_position_closed(
        self,
        order_id: str,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        quantity: float,
        fee: float = 0.0,
        opened_at: str | None = None,
    ) -> None:
        """Log a closed position with realised P&L (net of ``fee``).

        ``side`` is the side of the *opening* trade: ``buy`` for a long,
        ``sell`` for a short. P&L is expressed in quote currency.
        """
        side = side.lower()
        direction = 1.0 if side == "buy" else -1.0
        gross_pnl = direction * (exit_price - entry_price) * quantity
        pnl = gross_pnl - fee
        entry_notional = entry_price * quantity
        pnl_pct = (pnl / entry_notional) if entry_notional else 0.0
        self.log_decision(
            "position_closed",
            {
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "quantity": quantity,
                "fee": fee,
                "gross_pnl": gross_pnl,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "opened_at": opened_at,
            },
        )

    @staticmethod
    def _row_to_entry(row: Any) -> Dict[str, Any]:
        return {"timestamp": row["timestamp"], "event_type": row["event_type"], "data": json.loads(row["data"])}

    def read_all(self) -> List[Dict[str, Any]]:
        """Return every ledger entry in chronological (insertion) order."""
        with connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT timestamp, event_type, data FROM ledger_events ORDER BY id"
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def get_events(self, event_type: str) -> List[Dict[str, Any]]:
        """Return all entries matching ``event_type`` (chronological order, indexed)."""
        with connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT timestamp, event_type, data FROM ledger_events WHERE event_type=? ORDER BY id",
                (event_type,),
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def get_recent_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve the most recent entries (chronological order)."""
        with connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT timestamp, event_type, data FROM ledger_events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_entry(r) for r in reversed(rows)]
