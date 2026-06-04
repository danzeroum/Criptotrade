"""/v1/alerts — live SSE feed + paginated history of guardrail/risk alerts.

Trade-off: SSE (not WebSocket). Alerts are server→client only, so SSE is simpler
and proxy-friendly. The live stream is in-process (see :mod:`src.core.alerts`);
history is read from durable JSONL so a reconnecting client never sees an empty
feed.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sse_starlette.sse import EventSourceResponse

from src.api.deps import get_alert_bus, get_alert_store
from src.api.schemas import APIResponse, AlertOut, Meta
from src.core.alerts import AlertBus, AlertStore

router = APIRouter(prefix="/alerts", tags=["alerts"])

# Heartbeat keeps the connection (and proxies) alive when no alerts flow.
_HEARTBEAT_SECONDS = 15


@router.get(
    "",
    summary="Feed em tempo real de alertas (SSE)",
)
async def stream_alerts(
    request: Request,
    severity: Optional[str] = Query(None, pattern="^(low|medium|high|critical)$"),
    replay: int = Query(20, ge=0, le=200, description="Quantos alertas recentes reenviar ao abrir"),
    store: AlertStore = Depends(get_alert_store),
    bus: AlertBus = Depends(get_alert_bus),
) -> EventSourceResponse:
    async def event_generator():
        # 1) Replay recent history (chronological) so the client starts populated.
        recent, _ = store.history(severity=severity, limit=replay)
        for alert in reversed(recent):
            yield {"event": "alert", "id": alert["id"], "data": _json(alert)}

        # 2) Stream live alerts, with periodic heartbeats.
        queue = bus.register()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    alert = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SECONDS)
                except asyncio.TimeoutError:
                    yield {"event": "heartbeat", "data": "{}"}
                    continue
                if severity and alert.get("severity") != severity:
                    continue
                yield {"event": "alert", "id": alert["id"], "data": _json(alert)}
        finally:
            bus.unregister(queue)

    return EventSourceResponse(event_generator())


@router.get(
    "/history",
    response_model=APIResponse[list[AlertOut]],
    summary="Histórico paginado de alertas",
)
async def list_alerts_history(
    severity: Optional[str] = Query(None, pattern="^(low|medium|high|critical)$"),
    since: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    store: AlertStore = Depends(get_alert_store),
) -> APIResponse[list[AlertOut]]:
    rows, total = store.history(
        severity=severity, since=since, limit=limit, offset=(page - 1) * limit
    )
    return APIResponse(
        data=[AlertOut(**r) for r in rows],
        meta=Meta(total=total, page=page, per_page=limit),
    )


def _json(obj: dict) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)
