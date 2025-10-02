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

    def get_recent_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve recent trades from ledger."""
        if not self.ledger_path.exists():
            return []

        trades: List[Dict[str, Any]] = []
        with self.ledger_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    trades.append(json.loads(line))

        return trades[-limit:]
