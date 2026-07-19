"""N8² — DB-managed operated pairs (padrão A5: DB > env).

A row here means "the loop should trade this pair". When the table is non-empty,
:func:`src.core.pairs.operated_pairs` uses it instead of the ``SYMBOLS`` env
(the same DB-wins precedence as the exchange-connection factory). ``paused``
(N9) is read per-cycle by the loop — pausing never needs a restart; adding or
removing a pair does (the loop resolves its symbol list at boot).

All writes go through :meth:`add` / :meth:`remove` / :meth:`set_paused`; the
``config_changed`` audit event is emitted by the route, not here.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.core.db import connection

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OperatedPairStore:
    """CRUD over the ``operated_pairs`` table (app db)."""

    def list_all(self) -> List[Dict[str, Any]]:
        """All operated pairs, oldest first. ``[]`` if the table is absent."""
        try:
            with connection() as conn:
                rows = conn.execute(
                    "SELECT symbol, paused, added_at FROM operated_pairs ORDER BY added_at"
                ).fetchall()
            return [
                {"symbol": r["symbol"], "paused": bool(r["paused"]), "added_at": r["added_at"]}
                for r in rows
            ]
        except Exception:  # pragma: no cover - absent table => env fallback upstream
            return []

    def symbols(self) -> List[str]:
        """Just the symbols (paused or not — the loop filters paused per cycle)."""
        return [p["symbol"] for p in self.list_all()]

    def add(self, symbol: str) -> bool:
        """Insert a pair (idempotent). Returns True if it was newly added."""
        with connection() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO operated_pairs (symbol, paused, added_at)"
                " VALUES (?, 0, ?)",
                (symbol, _now()),
            )
            return cur.rowcount > 0

    def remove(self, symbol: str) -> bool:
        with connection() as conn:
            cur = conn.execute("DELETE FROM operated_pairs WHERE symbol = ?", (symbol,))
            return cur.rowcount > 0

    def set_paused(self, symbol: str, paused: bool) -> bool:
        """N9: pause/resume a pair (read per cycle by the loop). True if it exists."""
        with connection() as conn:
            cur = conn.execute(
                "UPDATE operated_pairs SET paused = ? WHERE symbol = ?",
                (1 if paused else 0, symbol),
            )
            return cur.rowcount > 0


__all__ = ["OperatedPairStore"]
