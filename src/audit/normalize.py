"""A4 audit trail: normalization envelope + indexed queries over the ledger.

The trail is a *read-side projection* of ``ledger_events`` — nothing is
re-written or duplicated. Each auditable event is normalized into the stable
envelope ``{id, ts, actor, action, entity, before, after, ip, ua, success,
detail}`` consumed by ``/v1/audit`` and the console's audit screen.

Filtering happens entirely in SQL (SQLite JSON1 ``json_extract``) so that
``meta.total`` and page boundaries are correct under ANY filter combination —
in particular the actor filter, whose value lives inside the JSON payload.
The SQL expressions below and the Python fallbacks in :func:`normalize` MUST
stay in lockstep: they are the same resolution rules in two languages.

Events with no recorded human/agent identity resolve to actor
``"orchestrator"`` (system events are attributable, never blank).
"""
from __future__ import annotations

import json
from typing import Any, Dict, Iterator, List, Optional, Tuple

from src.core.db import connection
from src.core.ledger import TradingLedger

# ------------------------------------------------------------- auditable scope
# The trail covers administrative/security/system-decision events — NOT the
# high-frequency telemetry (order_fill, signal_generated, risk_validation,
# process_event), which would drown the pages without audit value.
AUDIT_EXACT_TYPES: Tuple[str, ...] = (
    "hitl_approval",
    "hitl_level_changed",
    "config_changed",
    "position_closed",
    "circuit_breaker_tripped",
    "circuit_breaker_reset",
    "order_executed",
    "notification_sent",
    "notification_failed",
    "signal_skipped",
    "data_fallback",
)

_USER_MGMT_TYPES: Tuple[str, ...] = (
    "auth_user_invited",
    "auth_user_invite_resent",
    "auth_user_invite_revoked",
    "auth_user_role_changed",
    "auth_user_status_changed",
    "auth_user_deleted",
)

_AUDITABLE_SQL = (
    "(event_type LIKE 'auth\\_%' ESCAPE '\\'"
    " OR event_type LIKE 'connection\\_%' ESCAPE '\\'"
    " OR event_type LIKE 'apikey\\_%' ESCAPE '\\'"
    " OR event_type IN ("
    + ",".join("?" * len(AUDIT_EXACT_TYPES))
    + "))"
)

# Canonical actions surfaced by the API (see ACTIONS for the closed set).
ACTIONS: Tuple[str, ...] = (
    "login", "logout", "security", "user_management",
    "order_approved", "order_rejected", "autonomy_changed", "config_changed",
    "position_closed", "circuit_breaker", "order_executed", "notification",
    "connection", "platform_key", "signal_skipped", "data_fallback",
)

# ------------------------------------------------- actor/entity (SQL ↔ Python)
# NULLIF(..., '') mirrors Python's `or`, which treats '' as missing.
_ACTOR_SQL = (
    "COALESCE("
    "NULLIF(json_extract(data,'$.actor'),''),"
    "NULLIF(json_extract(data,'$.user'),''),"
    "NULLIF(json_extract(data,'$.operator'),''),"
    "NULLIF(json_extract(data,'$.agent'),''),"
    "'orchestrator')"
)

_ENTITY_SQL = (
    "COALESCE("
    "NULLIF(json_extract(data,'$.email'),''),"
    "NULLIF(json_extract(data,'$.order.pair'),''),"
    "NULLIF(json_extract(data,'$.scope'),''),"
    "NULLIF(json_extract(data,'$.symbol'),''),"
    "NULLIF(json_extract(data,'$.execution.symbol'),''),"
    "NULLIF(json_extract(data,'$.execution.pair'),''),"
    "NULLIF(json_extract(data,'$.label'),''),"
    "'')"
)


def _actor_of(data: Dict[str, Any]) -> str:
    return (
        data.get("actor") or data.get("user") or data.get("operator")
        or data.get("agent") or "orchestrator"
    )


def _entity_of(data: Dict[str, Any]) -> Optional[str]:
    order = data.get("order") or {}
    execution = data.get("execution") or {}
    return (
        data.get("email") or order.get("pair") or data.get("scope")
        or data.get("symbol") or execution.get("symbol") or execution.get("pair")
        or data.get("label") or None
    )


def action_of(event_type: str, data: Dict[str, Any]) -> str:
    if event_type == "auth_login":
        return "login"
    if event_type == "auth_logout":
        return "logout"
    if event_type in _USER_MGMT_TYPES:
        return "user_management"
    if event_type.startswith("auth_"):
        return "security"
    if event_type == "hitl_approval":
        return "order_approved" if data.get("approved") else "order_rejected"
    if event_type == "hitl_level_changed":
        return "autonomy_changed"
    if event_type in ("circuit_breaker_tripped", "circuit_breaker_reset"):
        return "circuit_breaker"
    if event_type in ("notification_sent", "notification_failed"):
        return "notification"
    if event_type.startswith("connection_"):
        return "connection"
    if event_type.startswith("apikey_"):
        return "platform_key"
    if event_type in (
        "config_changed", "position_closed", "order_executed", "signal_skipped", "data_fallback"
    ):
        return event_type
    return "other"


def _before_after(event_type: str, data: Dict[str, Any]):
    if event_type == "config_changed":
        return data.get("before"), data.get("after")
    if event_type == "hitl_level_changed":
        before = (
            {"level": data["previous_level"]} if "previous_level" in data else None
        )
        return before, {"level": data.get("level")}
    return None, None


def normalize(row_id: int, ts: str, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Map one raw ledger row to the audit envelope (dict, JSON-safe)."""
    before, after = _before_after(event_type, data)
    detail = data.get("detail") or data.get("reason") or None
    if event_type == "position_closed" and isinstance(data.get("pnl"), (int, float)):
        detail = f"P&L {data['pnl']:+.2f} USDT"
    success = data.get("success")
    return {
        "id": row_id,
        "ts": ts,
        "action": action_of(event_type, data),
        "actor": _actor_of(data),
        "entity": _entity_of(data),
        "ip": data.get("ip"),
        "ua": data.get("user_agent"),
        "success": success if isinstance(success, bool) else None,
        "before": before,
        "after": after,
        "detail": detail,
    }


# ------------------------------------------------------------------- filtering
def _like_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _action_predicate(action: str) -> Tuple[str, List[Any]]:
    if action == "login":
        return "event_type = 'auth_login'", []
    if action == "logout":
        return "event_type = 'auth_logout'", []
    if action == "user_management":
        marks = ",".join("?" * len(_USER_MGMT_TYPES))
        return f"event_type IN ({marks})", list(_USER_MGMT_TYPES)
    if action == "security":
        marks = ",".join("?" * len(_USER_MGMT_TYPES))
        return (
            "(event_type LIKE 'auth\\_%' ESCAPE '\\' "
            "AND event_type NOT IN ('auth_login','auth_logout') "
            f"AND event_type NOT IN ({marks}))",
            list(_USER_MGMT_TYPES),
        )
    if action == "order_approved":
        return "(event_type = 'hitl_approval' AND json_extract(data,'$.approved') = 1)", []
    if action == "order_rejected":
        return "(event_type = 'hitl_approval' AND json_extract(data,'$.approved') = 0)", []
    if action == "autonomy_changed":
        return "event_type = 'hitl_level_changed'", []
    if action == "circuit_breaker":
        return "event_type IN ('circuit_breaker_tripped','circuit_breaker_reset')", []
    if action == "notification":
        return "event_type IN ('notification_sent','notification_failed')", []
    if action == "connection":
        return "event_type LIKE 'connection\\_%' ESCAPE '\\'", []
    if action == "platform_key":
        return "event_type LIKE 'apikey\\_%' ESCAPE '\\'", []
    if action in (
        "config_changed", "position_closed", "order_executed", "signal_skipped", "data_fallback"
    ):
        return "event_type = ?", [action]
    raise ValueError(f"unknown audit action: {action}")


def _build_where(
    *,
    actor: Optional[str] = None,
    action: Optional[str] = None,
    entity: Optional[str] = None,
    since: Optional[str] = None,
    until_lt: Optional[str] = None,
    until_le: Optional[str] = None,
) -> Tuple[str, List[Any]]:
    clauses: List[str] = [_AUDITABLE_SQL]
    params: List[Any] = list(AUDIT_EXACT_TYPES)
    if action:
        pred, extra = _action_predicate(action)
        clauses.append(pred)
        params.extend(extra)
    if actor:
        clauses.append(f"{_ACTOR_SQL} = ?")
        params.append(actor)
    if entity:
        clauses.append(f"LOWER({_ENTITY_SQL}) LIKE ? ESCAPE '\\'")
        params.append(f"%{_like_escape(entity.lower())}%")
    if since:
        clauses.append("timestamp >= ?")
        params.append(since)
    if until_lt:
        clauses.append("timestamp < ?")
        params.append(until_lt)
    if until_le:
        clauses.append("timestamp <= ?")
        params.append(until_le)
    return " AND ".join(clauses), params


# --------------------------------------------------------------------- queries
_SELECT = "SELECT id, timestamp, event_type, data FROM ledger_events"


def read_audit_page(
    ledger: TradingLedger, *, limit: int = 50, offset: int = 0, **filters: Any
) -> Tuple[int, List[Dict[str, Any]]]:
    """One page (newest first) + the TOTAL under the same predicate.

    Every filter — actor included, via ``json_extract`` — is applied in SQL,
    so pages are always full and ``total`` is exact (A4 acceptance 2).
    """
    where, params = _build_where(**filters)
    with connection(ledger.db_path) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM ledger_events WHERE {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"{_SELECT} WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
    return total, [
        normalize(r["id"], r["timestamp"], r["event_type"], json.loads(r["data"]))
        for r in rows
    ]


def read_audit_event(ledger: TradingLedger, event_id: int) -> Optional[Dict[str, Any]]:
    """One envelope + the raw payload for the detail/diff view (None if the id
    is unknown OR points at a non-auditable event)."""
    where, params = _build_where()
    with connection(ledger.db_path) as conn:
        row = conn.execute(
            f"{_SELECT} WHERE id = ? AND {where}", (event_id, *params)
        ).fetchone()
    if row is None:
        return None
    data = json.loads(row["data"])
    envelope = normalize(row["id"], row["timestamp"], row["event_type"], data)
    envelope["event_type"] = row["event_type"]
    envelope["data"] = data
    return envelope


def iter_audit_events(
    ledger: TradingLedger, *, batch: int = 500, **filters: Any
) -> Iterator[Dict[str, Any]]:
    """Stream EVERY event matching the filters (newest first) — the export path
    must cover the complete filtered set, never a single page."""
    where, params = _build_where(**filters)
    with connection(ledger.db_path) as conn:
        cursor = conn.execute(
            f"{_SELECT} WHERE {where} ORDER BY id DESC", params
        )
        while True:
            rows = cursor.fetchmany(batch)
            if not rows:
                return
            for r in rows:
                yield normalize(
                    r["id"], r["timestamp"], r["event_type"], json.loads(r["data"])
                )


__all__ = [
    "ACTIONS", "AUDIT_EXACT_TYPES", "normalize", "action_of",
    "read_audit_page", "read_audit_event", "iter_audit_events",
]
