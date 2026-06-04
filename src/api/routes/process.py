"""/v1/process/events — the XES-style process event log.

Foundation for process mining (PM4Py) and the future "system health" view: each
order transition (submitted → filled/rejected/cancelled) is one event with
``case_id`` = order id.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_ledger
from src.api.schemas import APIResponse, Meta, ProcessEventOut
from src.core.ledger import TradingLedger

router = APIRouter(prefix="/process", tags=["process"])


@router.get(
    "/events",
    response_model=APIResponse[List[ProcessEventOut]],
    summary="Event log (XES) das transições de processo",
)
async def list_process_events(
    case_id: Optional[str] = Query(None, description="Filtra por uma instância (order id)"),
    limit: int = Query(200, ge=1, le=1000),
    ledger: TradingLedger = Depends(get_ledger),
) -> APIResponse[List[ProcessEventOut]]:
    events = ledger.get_process_events(case_id=case_id)
    rows = [
        ProcessEventOut(
            case_id=e["data"]["case_id"],
            activity=e["data"]["activity"],
            actor=e["data"]["actor"],
            timestamp=e["timestamp"],
            attributes=e["data"].get("attributes", {}),
        )
        for e in events[-limit:]
    ]
    return APIResponse(data=rows, meta=Meta(total=len(events), per_page=limit))
