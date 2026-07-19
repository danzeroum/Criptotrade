"""Persistence for notification channels/rules/settings + the dispatcher cursor.

Channel configs are JSON blobs **encrypted at rest** with the AUTH_SECRET_KEY
Fernet (``src/auth/security.py``) — the same contract A5 will use for exchange
keys. Reads for the API go through :func:`masked_config` so plaintext secrets
never leave the process; the PATCH flow treats an unchanged masked value as
"keep what is stored".
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from src.auth import security
from src.core.db import connection, get_db_path

CHANNEL_KINDS = ("email", "telegram", "slack", "webhook")
SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

# Fields that are secrets per kind (masked on read; PATCH keeps stored value
# when the client echoes the mask back unchanged).
SECRET_FIELDS = {
    "email": (),
    "telegram": ("bot_token",),
    "slack": ("webhook_url",),
    "webhook": ("url", "secret"),
}

MASK = "•••"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mask_value(field: str, value: str) -> str:
    if not value:
        return value
    if field in ("webhook_url", "url"):
        parts = urlsplit(value)
        return f"{parts.scheme}://{parts.netloc}/…"
    # tokens/secrets: keep the last 4 chars for recognition
    return f"{MASK}{value[-4:]}" if len(value) > 4 else MASK


def masked_config(kind: str, config: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(config)
    for field in SECRET_FIELDS.get(kind, ()):
        if out.get(field):
            out[field] = _mask_value(field, str(out[field]))
    return out


def masked_destination(kind: str, config: Dict[str, Any]) -> str:
    """Human destination for the UI ("Enviar teste para …") — never a secret."""
    if kind == "email":
        return config.get("to_email") or "—"
    if kind == "telegram":
        token = str(config.get("bot_token") or "")
        chat = config.get("chat_id") or "?"
        return f"chat {chat} · token {_mask_value('bot_token', token)}"
    if kind == "slack":
        return _mask_value("webhook_url", str(config.get("webhook_url") or ""))
    if kind == "webhook":
        return _mask_value("url", str(config.get("url") or ""))
    return "—"


class NotificationStore:
    """Channels + rules + settings + cursor over the main criptotrade.db."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db = db_path

    def _path(self):
        return self._db or get_db_path()

    @staticmethod
    def _row(r: Any) -> Dict[str, Any]:
        return {k: r[k] for k in r.keys()}

    # ---------------------------------------------------------------- channels
    def create_channel(self, kind: str, label: str, config: Dict[str, Any]) -> Dict[str, Any]:
        row = {
            "id": str(uuid.uuid4()), "kind": kind, "label": label,
            "config_enc": security.encrypt_secret(json.dumps(config, ensure_ascii=False)),
            "enabled": 1, "created_at": _now(),
        }
        with connection(self._path()) as conn:
            conn.execute(
                "INSERT INTO notification_channels (id, kind, label, config_enc,"
                " enabled, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (row["id"], kind, label, row["config_enc"], 1, row["created_at"]),
            )
        return self.get_channel(row["id"])

    def list_channels(self) -> List[Dict[str, Any]]:
        with connection(self._path()) as conn:
            rows = conn.execute(
                "SELECT * FROM notification_channels ORDER BY created_at"
            ).fetchall()
        return [self._row(r) for r in rows]

    def get_channel(self, channel_id: str) -> Optional[Dict[str, Any]]:
        with connection(self._path()) as conn:
            r = conn.execute(
                "SELECT * FROM notification_channels WHERE id = ?", (channel_id,)
            ).fetchone()
        return self._row(r) if r else None

    def channel_config(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt a channel row's config (empty dict if the key changed)."""
        raw = security.decrypt_secret(row["config_enc"])
        if raw is None:
            return {}
        try:
            return json.loads(raw)
        except ValueError:
            return {}

    def update_channel(self, channel_id: str, *, label: Optional[str] = None,
                       enabled: Optional[bool] = None,
                       config: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        row = self.get_channel(channel_id)
        if row is None:
            return None
        sets, params = [], []
        if label is not None:
            sets.append("label = ?")
            params.append(label)
        if enabled is not None:
            sets.append("enabled = ?")
            params.append(1 if enabled else 0)
        if config is not None:
            # PATCH contract: a secret field echoing the stored MASK unchanged
            # means "keep it" — merge before encrypting.
            stored = self.channel_config(row)
            merged = dict(config)
            for field in SECRET_FIELDS.get(row["kind"], ()):
                sent = merged.get(field)
                if sent and stored.get(field) and sent == _mask_value(field, str(stored[field])):
                    merged[field] = stored[field]
            sets.append("config_enc = ?")
            params.append(security.encrypt_secret(json.dumps(merged, ensure_ascii=False)))
        if sets:
            with connection(self._path()) as conn:
                conn.execute(
                    f"UPDATE notification_channels SET {', '.join(sets)} WHERE id = ?",
                    (*params, channel_id),
                )
        return self.get_channel(channel_id)

    def record_test(self, channel_id: str, ok: bool, error: Optional[str]) -> None:
        with connection(self._path()) as conn:
            conn.execute(
                "UPDATE notification_channels SET last_test_at = ?, last_test_ok = ?,"
                " last_error = ? WHERE id = ?",
                (_now(), 1 if ok else 0, error, channel_id),
            )

    def delete_channel(self, channel_id: str) -> bool:
        with connection(self._path()) as conn:
            cur = conn.execute(
                "DELETE FROM notification_channels WHERE id = ?", (channel_id,)
            )
            return cur.rowcount > 0

    # ------------------------------------------------------------------- rules
    def create_rule(self, alert_type: str, min_severity: str,
                    channel_ids: List[str],
                    pairs: Optional[List[str]] = None) -> Dict[str, Any]:
        rule_id = str(uuid.uuid4())
        pairs = pairs or ["*"]  # default: all pairs (N7 retrocompatible)
        with connection(self._path()) as conn:
            conn.execute(
                "INSERT INTO notification_rules (id, alert_type, min_severity,"
                " channel_ids, pairs, enabled, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
                (rule_id, alert_type, min_severity,
                 json.dumps(channel_ids), json.dumps(pairs), _now()),
            )
        return self.get_rule(rule_id)

    def list_rules(self) -> List[Dict[str, Any]]:
        with connection(self._path()) as conn:
            rows = conn.execute(
                "SELECT * FROM notification_rules ORDER BY created_at"
            ).fetchall()
        out = []
        for r in rows:
            row = self._row(r)
            row["channel_ids"] = json.loads(row["channel_ids"] or "[]")
            row["pairs"] = json.loads(row.get("pairs") or '["*"]')
            out.append(row)
        return out

    def get_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        with connection(self._path()) as conn:
            r = conn.execute(
                "SELECT * FROM notification_rules WHERE id = ?", (rule_id,)
            ).fetchone()
        if r is None:
            return None
        row = self._row(r)
        row["channel_ids"] = json.loads(row["channel_ids"] or "[]")
        row["pairs"] = json.loads(row.get("pairs") or '["*"]')
        return row

    def update_rule(self, rule_id: str, *, alert_type: Optional[str] = None,
                    min_severity: Optional[str] = None,
                    channel_ids: Optional[List[str]] = None,
                    pairs: Optional[List[str]] = None,
                    enabled: Optional[bool] = None) -> Optional[Dict[str, Any]]:
        if self.get_rule(rule_id) is None:
            return None
        sets, params = [], []
        if alert_type is not None:
            sets.append("alert_type = ?")
            params.append(alert_type)
        if min_severity is not None:
            sets.append("min_severity = ?")
            params.append(min_severity)
        if channel_ids is not None:
            sets.append("channel_ids = ?")
            params.append(json.dumps(channel_ids))
        if pairs is not None:
            sets.append("pairs = ?")
            params.append(json.dumps(pairs or ["*"]))
        if enabled is not None:
            sets.append("enabled = ?")
            params.append(1 if enabled else 0)
        if sets:
            with connection(self._path()) as conn:
                conn.execute(
                    f"UPDATE notification_rules SET {', '.join(sets)} WHERE id = ?",
                    (*params, rule_id),
                )
        return self.get_rule(rule_id)

    def delete_rule(self, rule_id: str) -> bool:
        with connection(self._path()) as conn:
            cur = conn.execute("DELETE FROM notification_rules WHERE id = ?", (rule_id,))
            return cur.rowcount > 0

    # ---------------------------------------------------------------- settings
    DEFAULT_SETTINGS = {
        "quiet_start": None, "quiet_end": None,
        "quiet_tz": "America/Sao_Paulo", "group_window_min": 5,
    }

    def get_settings(self) -> Dict[str, Any]:
        with connection(self._path()) as conn:
            r = conn.execute("SELECT * FROM notification_settings WHERE id = 1").fetchone()
        if r is None:
            return dict(self.DEFAULT_SETTINGS)
        row = self._row(r)
        row.pop("id", None)
        return row

    def set_settings(self, **fields: Any) -> Dict[str, Any]:
        merged = {**self.get_settings(), **{k: v for k, v in fields.items()
                                            if k in self.DEFAULT_SETTINGS}}
        with connection(self._path()) as conn:
            conn.execute(
                "INSERT INTO notification_settings (id, quiet_start, quiet_end,"
                " quiet_tz, group_window_min) VALUES (1, ?, ?, ?, ?)"
                " ON CONFLICT(id) DO UPDATE SET quiet_start = excluded.quiet_start,"
                " quiet_end = excluded.quiet_end, quiet_tz = excluded.quiet_tz,"
                " group_window_min = excluded.group_window_min",
                (merged["quiet_start"], merged["quiet_end"], merged["quiet_tz"],
                 merged["group_window_min"]),
            )
        return merged

    # ------------------------------------------------------------------ cursor
    def has_cursor(self) -> bool:
        with connection(self._path()) as conn:
            return conn.execute(
                "SELECT 1 FROM notifications_cursor WHERE id = 1"
            ).fetchone() is not None

    def get_cursor(self) -> int:
        with connection(self._path()) as conn:
            r = conn.execute("SELECT pos FROM notifications_cursor WHERE id = 1").fetchone()
        return int(r["pos"]) if r else 0

    def advance_cursor(self, expected: int, new_pos: int) -> bool:
        """Optimistic claim: only ONE dispatcher wins a batch even with N API
        workers — the loser sees rowcount 0 and skips (no double delivery)."""
        with connection(self._path()) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO notifications_cursor (id, pos, updated_at)"
                " VALUES (1, 0, ?)", (_now(),),
            )
            cur = conn.execute(
                "UPDATE notifications_cursor SET pos = ?, updated_at = ?"
                " WHERE id = 1 AND pos = ?",
                (new_pos, _now(), expected),
            )
            return cur.rowcount > 0

    def reset_cursor(self, pos: int) -> None:
        with connection(self._path()) as conn:
            conn.execute(
                "INSERT INTO notifications_cursor (id, pos, updated_at) VALUES (1, ?, ?)"
                " ON CONFLICT(id) DO UPDATE SET pos = excluded.pos,"
                " updated_at = excluded.updated_at",
                (pos, _now()),
            )


__all__ = ["NotificationStore", "CHANNEL_KINDS", "SEVERITY_ORDER",
           "masked_config", "masked_destination", "SECRET_FIELDS", "MASK"]
