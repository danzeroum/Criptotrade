"""/v1/process/events — the XES-style process event log.

Foundation for process mining (PM4Py) and the future "system health" view: each
order transition (submitted → filled/rejected/cancelled) is one event with
``case_id`` = order id.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_ledger
from src.api.schemas import APIResponse, Meta, ProcessEventOut, SkipOut
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


@router.get(
    "/skips",
    response_model=APIResponse[List[SkipOut]],
    summary="Decisões do ciclo: por que cada sinal não virou ordem (signal_skipped — N3)",
)
async def list_skips(
    symbol: Optional[str] = Query(None, description="Filtra por par (ex.: BTC/USDT)"),
    limit: int = Query(50, ge=1, le=500),
    ledger: TradingLedger = Depends(get_ledger),
) -> APIResponse[List[SkipOut]]:
    events = ledger.get_events("signal_skipped")
    if symbol:
        sym = symbol.upper()
        events = [e for e in events if str(e["data"].get("symbol", "")).upper() == sym]
    # Newest first — the feed shows current state + a compact history.
    rows = [
        SkipOut(
            symbol=e["data"].get("symbol", ""),
            reason=e["data"].get("reason", "unknown"),
            count=int(e["data"].get("count", 1) or 1),
            since=e["data"].get("since"),
            ts=e["timestamp"],
            confidence=e["data"].get("confidence"),
        )
        for e in reversed(events[-limit:])
    ]
    return APIResponse(data=rows, meta=Meta(total=len(events), per_page=limit))
