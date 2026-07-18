"""/v1/orders — submit orders and resolve pending HITL approvals.

Status codes carry meaning (so a client never mistakes a pending order for an
executed one):
* ``201 Created``  — order was auto-approved and filled immediately.
* ``202 Accepted`` — order is pending human approval.
* ``404`` unknown order · ``409`` order no longer pending · ``422`` bad input.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Response

from src.api.authn import Principal, require_perm
from src.api.deps import get_order_store
from src.api.schemas import APIResponse, Meta, OrderCreate, OrderDecisionPatch, OrderOut
from src.hitl.orders import Order, OrderConflictError, OrderStatus, OrderStore

router = APIRouter(prefix="/orders", tags=["orders"])


def _order_to_out(o: Order) -> OrderOut:
    d = o.to_dict()
    sl = d.get("stop_loss")
    tp = d.get("take_profit")
    px = d.get("price")
    if sl and tp and px and (px - sl) != 0:
        d["rr"] = round((tp - px) / (px - sl), 2)
    return OrderOut(**d)


@router.get(
    "",
    response_model=APIResponse[List[OrderOut]],
    summary="Lista ordens (filtra por status/par)",
)
async def list_orders(
    status: Optional[OrderStatus] = Query(None),
    pair: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    store: OrderStore = Depends(get_order_store),
) -> APIResponse[List[OrderOut]]:
    total = store.count(status=status, pair=pair)
    orders = store.list(status=status, pair=pair, limit=limit, offset=offset)
    return APIResponse(
        data=[_order_to_out(o) for o in orders],
        meta=Meta(total=total, page=offset // limit + 1, per_page=limit),
    )


@router.post(
    "",
    response_model=APIResponse[OrderOut],
    summary="Submete uma ordem (202 se pendente de HITL, 201 se auto-aprovada)",
    status_code=202,
)
async def create_order(
    response: Response,
    payload: OrderCreate = Body(...),
    store: OrderStore = Depends(get_order_store),
) -> APIResponse[OrderOut]:
    order = store.submit(
        Order(
            pair=payload.pair,
            side=payload.side.value,
            quantity=payload.quantity,
            price=payload.price,
            strategy=payload.strategy,
            agent_id=payload.agent_id,
            confidence=payload.confidence,
            reason=payload.reason,
            critical=payload.critical,
            position_size_pct=payload.position_size_pct,
            stop_loss=payload.stop_loss,
            take_profit=payload.take_profit,
        )
    )
    # 201 filled (auto-approved) · 202 pending HITL · 422 rejected by risk guardrails
    if order.status == OrderStatus.filled:
        response.status_code = 201
    elif order.status == OrderStatus.rejected:
        response.status_code = 422
    else:
        response.status_code = 202
    return APIResponse(data=OrderOut(**order.to_dict()))


@router.patch(
    "/{order_id}/status",
    response_model=APIResponse[OrderOut],
    summary="Operador aprova ou rejeita uma ordem pendente (ação HITL)",
)
async def decide_order(
    order_id: str = Path(...),
    patch: OrderDecisionPatch = Body(...),
    store: OrderStore = Depends(get_order_store),
    principal: Principal = Depends(require_perm("approve_order")),
) -> APIResponse[OrderOut]:
    if store.get(order_id) is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "order_not_found",
                "message": f"Ordem '{order_id}' não encontrada.",
            },
        )
    # A3: a real session stamps the authenticated identity — the client-sent
    # operator only survives for machine keys / legacy AUTH_MODE=off callers.
    operator = principal.actor if principal.kind == "user" else patch.operator
    try:
        order = store.resolve(
            order_id,
            approved=(patch.decision == "approve"),
            operator=operator,
            operator_note=patch.operator_note,
        )
    except OrderConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "order_not_pending",
                "message": str(exc),
                "current_status": exc.order.status.value,
            },
        ) from exc
    return APIResponse(data=OrderOut(**order.to_dict()))
