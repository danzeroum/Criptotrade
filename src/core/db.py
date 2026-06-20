"""SQLite backend for cross-process state (Phase 5a).

WAL mode gives concurrent readers + serialized writers across the two processes
(API and orchestrator loop) on the same host / local filesystem (see ADR-001 —
not valid over NFS). One **short-lived connection per operation** (the
:func:`connection` context manager) avoids sharing a ``Connection`` across
threads/coroutines.
"""
from __future__ import annotations

import contextlib
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional

# Repo-root/migrations (db.py is src/core/db.py).
MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def get_db_path(db_path: Optional[Path | str] = None) -> Path:
    """Resolve the SQLite file path (defaults to ``LEDGER_DIR/criptotrade.db``)."""
    if db_path is not None:
        return Path(db_path)
    base = Path(os.getenv("LEDGER_DIR", ".buildtovalue/ledger"))
    base.mkdir(parents=True, exist_ok=True)
    return base / "criptotrade.db"


@contextlib.contextmanager
def connection(db_path: Optional[Path | str] = None) -> Iterator[sqlite3.Connection]:
    """Open a short-lived connection, commit on success, rollback on error.

    PRAGMAs every connection: WAL (persistent, but cheap to re-assert),
    ``busy_timeout=5000`` (a contending writer waits 5s instead of raising
    ``SQLITE_BUSY``), and foreign keys on.
    """
    conn = sqlite3.connect(get_db_path(db_path), check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(
    db_path: Optional[Path | str] = None,
    migrations_dir: Optional[Path | str] = None,
) -> List[str]:
    """Apply pending migrations in filename order. Idempotent.

    Returns the list of migration versions applied on this call (empty if the DB
    was already up to date). Safe to call from both processes on startup.

    Migrations run **statement-by-statement inside the context manager's
    transaction** (not ``executescript``, which issues an implicit COMMIT and
    would leave a half-applied migration on failure). A failing migration is
    therefore rolled back atomically.
    """
    mdir = Path(migrations_dir) if migrations_dir else MIGRATIONS_DIR
    applied: List[str] = []
    with connection(db_path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        done = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations")}
        for sql_file in sorted(mdir.glob("*.sql")):
            version = sql_file.name
            if version in done:
                continue
            for statement in _split_sql_statements(sql_file.read_text(encoding="utf-8")):
                conn.execute(statement)
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (version, datetime.now(timezone.utc).isoformat()),
            )
            applied.append(version)
    return applied


def _split_sql_statements(sql: str) -> List[str]:
    """Split a migration file into individual statements.

    Strips ``--`` line comments then splits on ``;``. Adequate for the project's
    simple DDL migrations (no ``;`` or ``--`` inside string literals).
    """
    cleaned = "\n".join(line.split("--", 1)[0] for line in sql.splitlines())
    return [stmt.strip() for stmt in cleaned.split(";") if stmt.strip()]


__all__ = ["connection", "get_db_path", "init_db", "MIGRATIONS_DIR"]
