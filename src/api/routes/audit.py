"""/v1/audit — A4 audit trail (view_audit; operador+, machine keys, never demo).

Read-only projection over ``ledger_events`` (see src/audit/normalize.py).
List and export share ONE SQL predicate builder, so any filter combination —
actor included — yields full pages, an exact ``meta.total`` and an export that
covers the complete filtered set (not the visible page).
"""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterator, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse

from src.api.authn import require_perm
from src.api.deps import get_ledger
from src.api.schemas import APIResponse, AuditEventDetailOut, AuditEventOut, Meta
from src.audit import normalize as audit
from src.core.ledger import TradingLedger

router = APIRouter(prefix="/audit", tags=["audit"])


def _bad(field: str, message: str) -> HTTPException:
    return HTTPException(status_code=422, detail={
        "error": "validation_error", "message": message,
        "field": field, "docs": "/v1/docs",
    })


def _parse_filters(
    actor: Optional[str], action: Optional[str], entity: Optional[str],
    from_: Optional[str], to: Optional[str],
) -> Dict[str, Any]:
    """Validate query params and translate them into predicate kwargs.

    ``from``/``to`` accept a date (YYYY-MM-DD) or a full ISO timestamp; a bare
    ``to`` date is inclusive (internally: strictly before the next day).
    """
    if action and action not in audit.ACTIONS:
        raise _bad("action", f"Ação desconhecida. Use uma de: {', '.join(audit.ACTIONS)}.")
    filters: Dict[str, Any] = {"actor": actor, "action": action, "entity": entity}
    if from_:
        try:
            datetime.fromisoformat(from_)
        except ValueError:
            raise _bad("from", "Use uma data ISO (YYYY-MM-DD ou timestamp completo).")
        filters["since"] = from_
    if to:
        try:
            if len(to) == 10:
                filters["until_lt"] = (date.fromisoformat(to) + timedelta(days=1)).isoformat()
            else:
                datetime.fromisoformat(to)
                filters["until_le"] = to
        except ValueError:
            raise _bad("to", "Use uma data ISO (YYYY-MM-DD ou timestamp completo).")
    return {k: v for k, v in filters.items() if v}


@router.get(
    "",
    response_model=APIResponse[List[AuditEventOut]],
    summary="Trilha de auditoria paginada (filtros: actor, action, entity, from, to)",
    dependencies=[Depends(require_perm("view_audit"))],
)
async def list_audit(
    actor: Optional[str] = Query(None, max_length=200),
    action: Optional[str] = Query(None, max_length=40),
    entity: Optional[str] = Query(None, max_length=200),
    from_: Optional[str] = Query(None, alias="from", max_length=40),
    to: Optional[str] = Query(None, max_length=40),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ledger: TradingLedger = Depends(get_ledger),
) -> APIResponse[List[AuditEventOut]]:
    filters = _parse_filters(actor, action, entity, from_, to)
    total, events = audit.read_audit_page(ledger, limit=limit, offset=offset, **filters)
    return APIResponse(
        data=[AuditEventOut(**e) for e in events],
        meta=Meta(total=total, page=offset // limit + 1, per_page=limit),
    )


# ---------------------------------------------------------------------- export
_CSV_COLUMNS = ("id", "ts", "action", "actor", "entity", "ip", "ua",
                "success", "before", "after", "detail")


def _csv_cell(value: Any) -> Any:
    """Serialize one cell; neutralize spreadsheet formula injection.

    Cells starting with ``=``, ``+``, ``-`` or ``@`` are prefixed with a quote
    so Excel/Sheets render them as text instead of evaluating them (OWASP CSV
    injection).
    """
    if value is None:
        return ""
    if isinstance(value, dict):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    value = str(value)
    if value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _stream_csv(rows: Iterator[Dict[str, Any]]) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_CSV_COLUMNS)
    yield buffer.getvalue()
    for row in rows:
        buffer.seek(0)
        buffer.truncate()
        writer.writerow([_csv_cell(row.get(col)) for col in _CSV_COLUMNS])
        yield buffer.getvalue()


def _stream_json(rows: Iterator[Dict[str, Any]]) -> Iterator[str]:
    yield "["
    for i, row in enumerate(rows):
        yield ("," if i else "") + json.dumps(row, ensure_ascii=False)
    yield "]"


@router.get(
    "/export",
    summary="Exporta a trilha filtrada COMPLETA (CSV ou JSON, streaming)",
    dependencies=[Depends(require_perm("view_audit"))],
)
async def export_audit(
    format: str = Query("csv", pattern="^(csv|json)$"),
    actor: Optional[str] = Query(None, max_length=200),
    action: Optional[str] = Query(None, max_length=40),
    entity: Optional[str] = Query(None, max_length=200),
    from_: Optional[str] = Query(None, alias="from", max_length=40),
    to: Optional[str] = Query(None, max_length=40),
    ledger: TradingLedger = Depends(get_ledger),
) -> StreamingResponse:
    filters = _parse_filters(actor, action, entity, from_, to)
    rows = audit.iter_audit_events(ledger, **filters)
    if format == "json":
        stream, media = _stream_json(rows), "application/json"
    else:
        stream, media = _stream_csv(rows), "text/csv; charset=utf-8"
    stamp = datetime.now().strftime("%Y%m%d")
    return StreamingResponse(stream, media_type=media, headers={
        "Content-Disposition": f'attachment; filename="auditoria-{stamp}.{format}"',
    })


@router.get(
    "/{event_id}",
    response_model=APIResponse[AuditEventDetailOut],
    summary="Detalhe de um evento (envelope + payload bruto, com diff antes→depois)",
    dependencies=[Depends(require_perm("view_audit"))],
)
async def get_audit_event(
    event_id: int = Path(..., ge=1),
    ledger: TradingLedger = Depends(get_ledger),
) -> APIResponse[AuditEventDetailOut]:
    event = audit.read_audit_event(ledger, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail={
            "error": "audit_event_not_found",
            "message": f"Evento '{event_id}' não existe na trilha de auditoria.",
            "docs": "/v1/docs",
        })
    return APIResponse(data=AuditEventDetailOut(**event))
