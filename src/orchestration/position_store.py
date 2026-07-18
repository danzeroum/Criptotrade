"""SQLite persistence for the paper position book + circuit-breaker state.

Both must survive an orchestrator-loop restart. Without this the in-memory
position dict is lost on restart, leaving "zombie" open positions that never
close (CT-002), and the circuit breaker resets, forgetting a loss streak
(CT-004).

Best-effort by design: every operation creates its table if missing and never
raises into the trading path (a persistence failure must not break a trade that
already executed). The db path is resolved lazily through a provider so it tracks
the orchestrator's ledger db even when tests reassign it after construction.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

from src.core.db import connection, upsert as db_upsert

logger = logging.getLogger(__name__)

DbPathProvider = Callable[[], "Path | str"]

_CREATE_POSITIONS = """
CREATE TABLE IF NOT EXISTS open_positions (
    order_id    TEXT PRIMARY KEY,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL,
    entry_price REAL NOT NULL,
    quantity    REAL NOT NULL,
    stop_loss   REAL,
    take_profit REAL,
    opened_at   TEXT NOT NULL
)
"""

_CREATE_BREAKER = """
CREATE TABLE IF NOT EXISTS circuit_breaker_state (
    id                 INTEGER PRIMARY KEY CHECK (id = 1),
    tripped_at         REAL,
    consecutive_losses INTEGER NOT NULL DEFAULT 0,
    daily_loss_pct     REAL NOT NULL DEFAULT 0.0
)
"""


class PositionStore:
    """Best-effort SQLite mirror of the in-memory paper position book."""

    def __init__(self, db_path_provider: DbPathProvider) -> None:
        self._db = db_path_provider

    def upsert(self, order_id: str, pos: dict[str, Any]) -> None:
        try:
            with connection(self._db()) as conn:
                conn.execute(_CREATE_POSITIONS)
                cols = [
                    "order_id", "symbol", "side", "entry_price", "quantity",
                    "stop_loss", "take_profit", "opened_at",
                ]
                db_upsert(
                    conn, "open_positions", cols,
                    (
                        order_id, pos["symbol"], pos["side"], pos["entry_price"],
                        pos["quantity"], pos.get("stop_loss"), pos.get("take_profit"),
                        pos.get("opened_at"),
                    ),
                    conflict="order_id",
                    update_cols=cols[1:],
                )
        except Exception:  # pragma: no cover - persistence must never break a trade
            logger.warning("PositionStore.upsert failed for %s", order_id, exc_info=True)

    def delete(self, order_id: str) -> None:
        try:
            with connection(self._db()) as conn:
                conn.execute(_CREATE_POSITIONS)
                conn.execute("DELETE FROM open_positions WHERE order_id=?", (order_id,))
        except Exception:  # pragma: no cover
            logger.warning("PositionStore.delete failed for %s", order_id, exc_info=True)

    def count(self) -> int:
        """Return the number of currently open positions (best-effort; 0 on error)."""
        try:
            with connection(self._db()) as conn:
                conn.execute(_CREATE_POSITIONS)
                row = conn.execute("SELECT COUNT(*) FROM open_positions").fetchone()
                return int(row[0]) if row else 0
        except Exception:  # pragma: no cover - persistence must never break a scrape
            logger.warning("PositionStore.count failed", exc_info=True)
            return 0

    def load_all(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        try:
            with connection(self._db()) as conn:
                conn.execute(_CREATE_POSITIONS)
                rows = conn.execute(
                    "SELECT order_id, symbol, side, entry_price, quantity,"
                    " stop_loss, take_profit, opened_at FROM open_positions"
                ).fetchall()
            for r in rows:
                out[r["order_id"]] = {
                    "symbol": r["symbol"], "side": r["side"],
                    "entry_price": r["entry_price"], "quantity": r["quantity"],
                    "stop_loss": r["stop_loss"], "take_profit": r["take_profit"],
                    "opened_at": r["opened_at"],
                }
        except Exception:  # pragma: no cover
            logger.warning("PositionStore.load_all failed", exc_info=True)
        return out


def save_circuit_state(
    db_path_provider: DbPathProvider,
    tripped_at: Optional[float],
    consecutive_losses: int,
    daily_loss_pct: float,
) -> None:
    """Persist the single-row circuit-breaker state (best-effort)."""
    try:
        with connection(db_path_provider()) as conn:
            conn.execute(_CREATE_BREAKER)
            db_upsert(
                conn, "circuit_breaker_state",
                ["id", "tripped_at", "consecutive_losses", "daily_loss_pct"],
                (1, tripped_at, consecutive_losses, daily_loss_pct),
                conflict="id",
                update_cols=["tripped_at", "consecutive_losses", "daily_loss_pct"],
            )
    except Exception:  # pragma: no cover
        logger.warning("save_circuit_state failed", exc_info=True)


def load_circuit_state(db_path_provider: DbPathProvider) -> Optional[dict[str, Any]]:
    """Load the circuit-breaker state, or None if never persisted (best-effort)."""
    try:
        with connection(db_path_provider()) as conn:
            conn.execute(_CREATE_BREAKER)
            row = conn.execute(
                "SELECT tripped_at, consecutive_losses, daily_loss_pct"
                " FROM circuit_breaker_state WHERE id=1"
            ).fetchone()
        if row is None:
            return None
        return {
            "tripped_at": row["tripped_at"],
            "consecutive_losses": row["consecutive_losses"],
            "daily_loss_pct": row["daily_loss_pct"],
        }
    except Exception:  # pragma: no cover
        logger.warning("load_circuit_state failed", exc_info=True)
        return None


__all__ = ["PositionStore", "save_circuit_state", "load_circuit_state"]
