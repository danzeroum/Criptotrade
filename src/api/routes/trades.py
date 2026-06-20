"""GET /v1/trades/closed — realised paper trades (per-trade P&L) from the ledger.

Closed-trade history was previously only reachable by reading the raw
process-event log; this endpoint exposes it directly with pagination and an
optional symbol filter (CT-006).
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_ledger
from src.api.schemas import APIResponse, ClosedTradeOut, Meta
from src.core.ledger import TradingLedger
from src.core.pairs import allowed_pairs, is_allowed

router = APIRouter(prefix="/trades", tags=["trades"])


def _validated_symbol(symbol: Optional[str]) -> Optional[str]:
    if symbol is None or not symbol.strip():
        return None
    sym = symbol.replace("-", "/").upper() if "/" not in symbol else symbol.upper()
    if not is_allowed(sym):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_pair",
                "message": f"Par '{sym}' não permitido.",
                "valid": allowed_pairs(),
                "docs": "/v1/docs",
            },
        )
    return sym


@router.get(
    "/closed",
    response_model=APIResponse[List[ClosedTradeOut]],
    summary="Histórico de trades fechados com P&L individual",
)
async def list_closed_trades(
    symbol: Optional[str] = Query(None, description="Filtrar por par (ex.: BTC/USDT)."),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ledger: TradingLedger = Depends(get_ledger),
) -> APIResponse[List[ClosedTradeOut]]:
    sym = _validated_symbol(symbol)
    events = [
        e
        for e in ledger.get_events("position_closed")
        if sym is None or str(e.get("data", {}).get("symbol", "")).upper() == sym
    ]
    events.reverse()  # most recent first
    total = len(events)
    page = events[offset : offset + limit]

    trades: List[ClosedTradeOut] = []
    for e in page:
        d = e.get("data", {})
        trades.append(
            ClosedTradeOut(
                order_id=d.get("order_id", ""),
                symbol=d.get("symbol", ""),
                side=d.get("side", ""),
                entry_price=d.get("entry_price", 0.0),
                exit_price=d.get("exit_price", 0.0),
                quantity=d.get("quantity", 0.0),
                fee=d.get("fee", 0.0) or 0.0,
                pnl=d.get("pnl", 0.0),
                pnl_pct=d.get("pnl_pct", 0.0),
                opened_at=d.get("opened_at"),
                closed_at=e.get("timestamp"),
            )
        )

    return APIResponse(
        data=trades,
        meta=Meta(total=total, page=offset // limit + 1, per_page=limit),
    )
