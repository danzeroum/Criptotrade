"""Immutable audit ledger for all trading decisions."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class TradingLedger:
    """Append-only ledger for audit trail."""

    def __init__(self, ledger_path: Path | None = None) -> None:
        self.ledger_path = ledger_path or Path(".buildtovalue/ledger/trades.jsonl")
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    def log_decision(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log a trading decision to the ledger."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "data": data,
        }

        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.info("Ledger entry recorded", extra={"event_type": event_type})

    def log_signal(self, agent: str, signal: Dict[str, Any]) -> None:
        """Log a trading signal."""
        self.log_decision(
            "signal_generated",
            {
                "agent": agent,
                "signal": signal,
            },
        )

    def log_validation(self, agent: str, validation: Dict[str, Any]) -> None:
        """Log a risk validation."""
        self.log_decision(
            "risk_validation",
            {
                "agent": agent,
                "validation": validation,
            },
        )

    def log_execution(self, agent: str, execution: Dict[str, Any]) -> None:
        """Log an order execution."""
        self.log_decision(
            "order_executed",
            {
                "agent": agent,
                "execution": execution,
            },
        )

    def log_hitl_approval(self, approved: bool, order: Dict[str, Any], user: str = "default") -> None:
        """Log human-in-the-loop approval decision."""
        self.log_decision(
            "hitl_approval",
            {
                "approved": approved,
                "order": order,
                "user": user,
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
            {
                "case_id": case_id,
                "activity": activity,
                "actor": actor,
                "attributes": attributes or {},
            },
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

    def read_all(self) -> List[Dict[str, Any]]:
        """Return every ledger entry in chronological (append) order."""
        if not self.ledger_path.exists():
            return []

        entries: List[Dict[str, Any]] = []
        with self.ledger_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    entries.append(json.loads(line))
        return entries

    def get_events(self, event_type: str) -> List[Dict[str, Any]]:
        """Return all entries matching ``event_type`` (chronological order)."""
        return [e for e in self.read_all() if e.get("event_type") == event_type]

    def get_recent_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve recent trades from ledger."""
        return self.read_all()[-limit:]
