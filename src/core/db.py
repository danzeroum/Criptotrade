"""Database backend for cross-process state.

**Default: SQLite (WAL)** — one short-lived connection per operation, no shared
``Connection`` across threads/coroutines (ADR-001 / ADR-003).

**Optional: PostgreSQL** — set ``DATABASE_URL=postgresql://user:pass@host/db`` to
run the shared state on Postgres, enabling horizontal scale (multiple hosts
writing state — ADR-005). The same call sites work on both backends via a thin
compatibility layer:

* ``?`` placeholders are translated to ``%s`` on Postgres;
* rows support both ``row[0]`` and ``row["col"]`` (like ``sqlite3.Row``);
* :func:`upsert` emits ``INSERT OR REPLACE/IGNORE`` (SQLite) or
  ``INSERT ... ON CONFLICT`` (Postgres);
* :func:`autoincrement_pk` emits the right PK clause.

DDL lives in ``migrations/`` (SQLite) and ``migrations/postgres/`` (Postgres).
"""
from __future__ import annotations

import contextlib
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, List, Optional, Sequence

# Repo-root/migrations (db.py is src/core/db.py).
MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


# --------------------------------------------------------------- backend select
def _database_url() -> Optional[str]:
    """Return the Postgres URL if ``DATABASE_URL`` points at Postgres, else None."""
    url = os.getenv("DATABASE_URL", "").strip()
    return url if url.startswith(("postgres://", "postgresql://")) else None


def is_postgres() -> bool:
    """True when the shared state runs on PostgreSQL (``DATABASE_URL`` set)."""
    return _database_url() is not None


def autoincrement_pk() -> str:
    """Auto-incrementing integer PK clause for the active backend."""
    return "BIGSERIAL PRIMARY KEY" if is_postgres() else "INTEGER PRIMARY KEY AUTOINCREMENT"


def get_db_path(db_path: Optional[Path | str] = None) -> Path:
    """Resolve the SQLite file path (defaults to ``LEDGER_DIR/criptotrade.db``)."""
    if db_path is not None:
        return Path(db_path)
    base = Path(os.getenv("LEDGER_DIR", ".buildtovalue/ledger"))
    base.mkdir(parents=True, exist_ok=True)
    return base / "criptotrade.db"


# --------------------------------------------------------------- postgres glue
class _Row:  # pragma: no cover - Postgres-only; covered by tests/integration/test_postgres_backend.py
    """Mapping+sequence row (like ``sqlite3.Row``): supports ``row[0]`` and ``row['c']``."""

    __slots__ = ("_cols", "_vals", "_map")

    def __init__(self, cols: Sequence[str], vals: Sequence[Any]) -> None:
        self._cols = list(cols)
        self._vals = list(vals)
        self._map = dict(zip(self._cols, self._vals))

    def __getitem__(self, key: Any) -> Any:
        return self._vals[key] if isinstance(key, int) else self._map[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._map.get(key, default)

    def keys(self) -> List[str]:
        return list(self._cols)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._vals)

    def __len__(self) -> int:
        return len(self._vals)


def _hybrid_row_factory(cursor: Any):  # pragma: no cover - Postgres-only (gated PG test)
    """psycopg row factory producing :class:`_Row` (so ``dict(row)`` also works)."""
    cols = [c.name for c in (cursor.description or [])]

    def make(values: Sequence[Any]) -> _Row:
        return _Row(cols, values)

    return make


class _PgConn:  # pragma: no cover - Postgres-only (gated PG test)
    """Adapts a psycopg connection to the sqlite3-style API used by call sites."""

    def __init__(self, raw: Any) -> None:
        self._raw = raw

    def execute(self, sql: str, params: Sequence[Any] = ()) -> Any:
        return self._raw.execute(sql.replace("?", "%s"), tuple(params))

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def close(self) -> None:
        self._raw.close()


def _pg_connect() -> Any:  # pragma: no cover - Postgres-only (gated PG test)
    import psycopg

    return psycopg.connect(_database_url(), row_factory=_hybrid_row_factory, autocommit=False)


# --------------------------------------------------------------- connection
@contextlib.contextmanager
def connection(db_path: Optional[Path | str] = None) -> Iterator[Any]:
    """Open a short-lived connection; commit on success, rollback on error.

    SQLite: WAL + ``busy_timeout`` + foreign keys, ``sqlite3.Row`` rows. Postgres:
    a compatibility wrapper (``?``→``%s``, hybrid rows); ``db_path`` is ignored
    (the URL is the single shared database).
    """
    if is_postgres():  # pragma: no cover - Postgres-only (gated PG test)
        raw = _pg_connect()
        try:
            yield _PgConn(raw)
            raw.commit()
        except Exception:
            raw.rollback()
            raise
        finally:
            raw.close()
        return

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


# --------------------------------------------------------------- upsert helper
def upsert(
    conn: Any,
    table: str,
    columns: Sequence[str],
    values: Sequence[Any],
    conflict: str,
    update_cols: Optional[Sequence[str]] = None,
) -> None:
    """Backend-aware upsert.

    ``update_cols`` set → REPLACE / ``DO UPDATE``; None → IGNORE / ``DO NOTHING``.
    """
    cols = ", ".join(columns)
    placeholders = ", ".join("?" for _ in columns)
    if is_postgres():  # pragma: no cover - Postgres-only (gated PG test)
        base = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        if update_cols:
            setters = ", ".join(f"{c}=EXCLUDED.{c}" for c in update_cols)
            sql = f"{base} ON CONFLICT ({conflict}) DO UPDATE SET {setters}"
        else:
            sql = f"{base} ON CONFLICT ({conflict}) DO NOTHING"
    else:
        verb = "INSERT OR REPLACE" if update_cols else "INSERT OR IGNORE"
        sql = f"{verb} INTO {table} ({cols}) VALUES ({placeholders})"
    conn.execute(sql, values)


# --------------------------------------------------------------- migrations
def _resolve_migrations_dir(migrations_dir: Optional[Path | str]) -> Path:
    if migrations_dir is not None:
        return Path(migrations_dir)
    return MIGRATIONS_DIR / "postgres" if is_postgres() else MIGRATIONS_DIR


def init_db(
    db_path: Optional[Path | str] = None,
    migrations_dir: Optional[Path | str] = None,
) -> List[str]:
    """Apply pending migrations in filename order. Idempotent.

    Returns the versions applied on this call (empty if already up to date). Safe
    to call from both processes on startup. Migrations run statement-by-statement
    inside the transaction, so a failing migration rolls back atomically.
    """
    mdir = _resolve_migrations_dir(migrations_dir)
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
            upsert(
                conn,
                "schema_migrations",
                ["version", "applied_at"],
                (version, datetime.now(timezone.utc).isoformat()),
                conflict="version",
            )
            applied.append(version)
    return applied


def _split_sql_statements(sql: str) -> List[str]:
    """Split a migration file into statements (strip ``--`` comments, split on ``;``)."""
    cleaned = "\n".join(line.split("--", 1)[0] for line in sql.splitlines())
    return [stmt.strip() for stmt in cleaned.split(";") if stmt.strip()]


__all__ = [
    "connection",
    "get_db_path",
    "init_db",
    "is_postgres",
    "autoincrement_pk",
    "upsert",
    "MIGRATIONS_DIR",
]
