"""Persistence for exchange connections and platform API keys (A5).

Exchange credentials are a Fernet-encrypted JSON blob (AUTH_SECRET_KEY — the
6b contract): the API key is shown MASKED, the secret NEVER leaves the process
in any form after creation. At most ONE connection is active; the live-routing
gate in ``src/core/exchange_factory.py`` reads it.

Platform keys are hash-only (sha256) for authentication — the full ``ctk_…``
token exists exactly once, in the creation response. ``key_prefix`` is stored
purely for display so an admin can correlate keys with integrations (nota 3).
"""
from __future__ import annotations

import hashlib
import json
import secrets as _secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.auth import security
from src.core.db import connection, get_db_path

CONNECTION_SCOPES = ("read", "trade")
KEY_SCOPES = ("visualizador", "operador", "admin")

MASK = "•••"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mask_value(value: str) -> str:
    if not value:
        return value
    return f"{MASK}{value[-4:]}" if len(value) > 4 else MASK


def redact(text: str, *secret_values: Optional[str]) -> str:
    """Scrub secrets out of any outbound text (errors, logs, ledger payloads).
    The A5 hard guardrail: no secret in a response, exception or log line."""
    out = text or ""
    for value in secret_values:
        if value and len(value) >= 6:
            out = out.replace(value, mask_value(value))
    return out


class ConnectionStore:
    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db = db_path

    def _path(self):
        return self._db or get_db_path()

    @staticmethod
    def _row(r: Any) -> Dict[str, Any]:
        return {k: r[k] for k in r.keys()}

    def create(self, exchange_id: str, label: str, api_key: str, api_secret: str,
               *, scope: str = "read", testnet: bool = True) -> Dict[str, Any]:
        row_id = str(uuid.uuid4())
        config_enc = security.encrypt_secret(
            json.dumps({"api_key": api_key, "api_secret": api_secret})
        )
        with connection(self._path()) as conn:
            conn.execute(
                "INSERT INTO exchange_connections (id, exchange_id, label, config_enc,"
                " scope, testnet, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
                (row_id, exchange_id, label, config_enc, scope,
                 1 if testnet else 0, _now()),
            )
        return self.get(row_id)

    def list(self) -> List[Dict[str, Any]]:
        with connection(self._path()) as conn:
            rows = conn.execute(
                "SELECT * FROM exchange_connections ORDER BY created_at"
            ).fetchall()
        return [self._row(r) for r in rows]

    def get(self, conn_id: str) -> Optional[Dict[str, Any]]:
        with connection(self._path()) as conn:
            r = conn.execute(
                "SELECT * FROM exchange_connections WHERE id = ?", (conn_id,)
            ).fetchone()
        return self._row(r) if r else None

    def get_active(self) -> Optional[Dict[str, Any]]:
        with connection(self._path()) as conn:
            r = conn.execute(
                "SELECT * FROM exchange_connections WHERE is_active = 1"
                " AND revoked_at IS NULL LIMIT 1"
            ).fetchone()
        return self._row(r) if r else None

    def config(self, row: Dict[str, Any]) -> Dict[str, Any]:
        raw = security.decrypt_secret(row["config_enc"])
        if raw is None:
            return {}
        try:
            return json.loads(raw)
        except ValueError:
            return {}

    def activate(self, conn_id: str) -> bool:
        """Atomically make ``conn_id`` the single active connection."""
        with connection(self._path()) as conn:
            cur = conn.execute(
                "UPDATE exchange_connections SET is_active = 1"
                " WHERE id = ? AND revoked_at IS NULL",
                (conn_id,),
            )
            if cur.rowcount == 0:
                return False
            conn.execute(
                "UPDATE exchange_connections SET is_active = 0 WHERE id != ?",
                (conn_id,),
            )
            return True

    def rotate(self, conn_id: str, *, api_secret: str,
               api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Swap credentials and RESET the test status (fail-safe: the live gate
        refuses to boot until the rotated connection is re-tested)."""
        row = self.get(conn_id)
        if row is None or row["revoked_at"]:
            return None
        stored = self.config(row)
        merged = {"api_key": api_key or stored.get("api_key"), "api_secret": api_secret}
        with connection(self._path()) as conn:
            conn.execute(
                "UPDATE exchange_connections SET config_enc = ?, last_test_at = NULL,"
                " last_test_ok = NULL, last_test_detail = NULL WHERE id = ?",
                (security.encrypt_secret(json.dumps(merged)), conn_id),
            )
        return self.get(conn_id)

    def record_test(self, conn_id: str, ok: bool, detail: Dict[str, Any]) -> None:
        with connection(self._path()) as conn:
            conn.execute(
                "UPDATE exchange_connections SET last_test_at = ?, last_test_ok = ?,"
                " last_test_detail = ? WHERE id = ?",
                (_now(), 1 if ok else 0, json.dumps(detail, ensure_ascii=False), conn_id),
            )

    def revoke(self, conn_id: str) -> bool:
        with connection(self._path()) as conn:
            cur = conn.execute(
                "UPDATE exchange_connections SET revoked_at = ?, is_active = 0"
                " WHERE id = ? AND revoked_at IS NULL",
                (_now(), conn_id),
            )
            return cur.rowcount > 0


class PlatformKeyStore:
    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db = db_path

    def _path(self):
        return self._db or get_db_path()

    @staticmethod
    def _row(r: Any) -> Dict[str, Any]:
        return {k: r[k] for k in r.keys()}

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def create(self, label: str, scope: str, created_by: str) -> Tuple[Dict[str, Any], str]:
        """Mint a key. Returns (row, FULL token) — the only time it exists."""
        token = "ctk_" + _secrets.token_urlsafe(24)
        row_id = str(uuid.uuid4())
        with connection(self._path()) as conn:
            conn.execute(
                "INSERT INTO platform_api_keys (id, label, key_prefix, key_hash,"
                " scope, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (row_id, label, token[:12], self._hash(token), scope,
                 created_by, _now()),
            )
        return self.get(row_id), token

    def list(self) -> List[Dict[str, Any]]:
        with connection(self._path()) as conn:
            rows = conn.execute(
                "SELECT * FROM platform_api_keys ORDER BY created_at"
            ).fetchall()
        return [self._row(r) for r in rows]

    def get(self, key_id: str) -> Optional[Dict[str, Any]]:
        with connection(self._path()) as conn:
            r = conn.execute(
                "SELECT * FROM platform_api_keys WHERE id = ?", (key_id,)
            ).fetchone()
        return self._row(r) if r else None

    def resolve(self, token: str) -> Optional[Dict[str, Any]]:
        """Authenticate a presented token: active row or None. Stamps
        ``last_used_at`` on success (the A5 'último uso' display)."""
        th = self._hash(token)
        with connection(self._path()) as conn:
            r = conn.execute(
                "SELECT * FROM platform_api_keys WHERE key_hash = ?"
                " AND revoked_at IS NULL",
                (th,),
            ).fetchone()
            if r is None:
                return None
            conn.execute(
                "UPDATE platform_api_keys SET last_used_at = ? WHERE id = ?",
                (_now(), r["id"]),
            )
            return self._row(r)

    def revoke(self, key_id: str) -> bool:
        with connection(self._path()) as conn:
            cur = conn.execute(
                "UPDATE platform_api_keys SET revoked_at = ? WHERE id = ?"
                " AND revoked_at IS NULL",
                (_now(), key_id),
            )
            return cur.rowcount > 0


__all__ = ["ConnectionStore", "PlatformKeyStore", "CONNECTION_SCOPES",
           "KEY_SCOPES", "mask_value", "redact"]
