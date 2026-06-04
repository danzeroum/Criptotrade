"""HITL order bridge — pending-order store + lifecycle.

This is the bridge the validation doc called for: a place where an order can sit
in ``pending`` until a human resolves it, while the autonomy level decides what
gets auto-approved.

Lifecycle::

    pending ──approve──► filled        (logs a fill to the ledger)
       │
       └────reject───►  rejected       (requires operator_note)

Auto-approval rule (mirrors the operator-facing autonomy levels):
    notional <= level threshold (USD) AND not critical  → auto-approve & fill
    otherwise                                            → pending (await human)

So level 0 (threshold 0) makes every order pending; level 3 auto-approves up to
$5,000 but still routes ``critical`` orders to a human.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from src.core.ledger import TradingLedger


class OrderStatus(str, Enum):
    pending = "pending"
    filled = "filled"
    rejected = "rejected"
    cancelled = "cancelled"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Order:
    pair: str
    side: str
    quantity: float
    price: float
    strategy: str
    agent_id: str
    confidence: float
    reason: str
    critical: bool = False
    status: OrderStatus = OrderStatus.pending
    operator_note: Optional[str] = None
    operator_id: Optional[str] = None
    auto_approved: bool = False
    id: str = field(default_factory=lambda: "ord_" + uuid.uuid4().hex[:8])
    created_at: str = field(default_factory=_now)
    resolved_at: Optional[str] = None
    filled_at: Optional[str] = None

    @property
    def notional(self) -> float:
        return self.price * self.quantity

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["notional"] = self.notional
        return data


class OrderConflictError(Exception):
    """Raised when transitioning an order that is no longer ``pending``."""

    def __init__(self, order: Order) -> None:
        self.order = order
        super().__init__(f"Order {order.id} is '{order.status.value}', not pending")


class OrderStore:
    """In-memory order store with a ledger-backed fill side effect.

    ``threshold_provider`` returns the current autonomy USD threshold (typically
    ``HITLConfigStore`` level threshold), so auto-approval tracks the live level.
    """

    def __init__(
        self,
        ledger: TradingLedger,
        threshold_provider: Callable[[], float],
        decision_timeout: float = 300.0,
    ) -> None:
        self._ledger = ledger
        self._threshold_provider = threshold_provider
        # Pending orders with no human response within this window are auto-
        # cancelled (fail-closed): a stuck approval must never block forever.
        self._decision_timeout = decision_timeout
        self._orders: Dict[str, Order] = {}
        self._events: Dict[str, asyncio.Event] = {}

    # ------------------------------------------------------------------ submit
    def submit(self, order: Order) -> Order:
        """Register an order; auto-approve+fill it or leave it pending."""
        self._orders[order.id] = order
        self._events[order.id] = asyncio.Event()
        self._ledger.log_process_event(
            order.id, "order_submitted", order.agent_id,
            {"pair": order.pair, "side": order.side, "notional": order.notional},
        )

        threshold = self._threshold_provider()
        auto = (threshold > 0) and (order.notional <= threshold) and not order.critical
        if auto:
            order.auto_approved = True
            self._fill(order, operator="auto")
        return order

    # ------------------------------------------------------------------ resolve
    def resolve(
        self,
        order_id: str,
        approved: bool,
        operator: str = "operator",
        operator_note: Optional[str] = None,
    ) -> Order:
        """Human decision on a pending order. Raises if it is not pending."""
        order = self.get(order_id)
        if order is None:
            raise KeyError(order_id)
        if order.status != OrderStatus.pending:
            raise OrderConflictError(order)

        order.operator_id = operator
        order.operator_note = operator_note
        if approved:
            self._fill(order, operator=operator)
        else:
            order.status = OrderStatus.rejected
            order.resolved_at = _now()
            self._ledger.log_hitl_approval(approved=False, order=order.to_dict(), user=operator)
            self._ledger.log_process_event(
                order.id, "order_rejected", operator, {"note": operator_note},
            )
        self._signal(order_id)
        return order

    def cancel(self, order_id: str, reason: str = "timeout") -> Optional[Order]:
        """Cancel a pending order (e.g. on decision timeout). Idempotent."""
        order = self.get(order_id)
        if order is None or order.status != OrderStatus.pending:
            return order
        order.status = OrderStatus.cancelled
        order.resolved_at = _now()
        order.operator_note = reason
        self._ledger.log_process_event(order.id, "order_cancelled", "system", {"reason": reason})
        self._signal(order_id)
        return order

    # ------------------------------------------------------------------ queries
    def get(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def list(
        self, status: Optional[OrderStatus] = None, pair: Optional[str] = None
    ) -> List[Order]:
        orders = list(self._orders.values())
        if status is not None:
            orders = [o for o in orders if o.status == status]
        if pair is not None:
            orders = [o for o in orders if o.pair == pair]
        orders.sort(key=lambda o: o.created_at, reverse=True)
        return orders

    def pending_count(self) -> int:
        return sum(1 for o in self._orders.values() if o.status == OrderStatus.pending)

    # ------------------------------------------------------------------ bridge
    async def wait_for_decision(self, order_id: str) -> bool:
        """Await a human decision; returns ``True`` if the order was filled.

        Used by an orchestrator ``approval_handler`` so a running pipeline can
        block on the same store the PATCH endpoint resolves. Fail-closed: if no
        decision arrives within ``decision_timeout`` seconds the order is
        auto-cancelled and ``False`` is returned — a stuck approval never blocks
        the pipeline forever.
        """
        event = self._events.get(order_id)
        if event is None:
            return False
        try:
            await asyncio.wait_for(event.wait(), timeout=self._decision_timeout)
        except asyncio.TimeoutError:
            self.cancel(order_id, reason="decision_timeout")
            return False
        order = self._orders[order_id]
        return order.status == OrderStatus.filled

    # ------------------------------------------------------------------ helpers
    def _fill(self, order: Order, operator: str) -> None:
        order.status = OrderStatus.filled
        order.resolved_at = _now()
        order.filled_at = order.resolved_at
        self._ledger.log_hitl_approval(approved=True, order=order.to_dict(), user=operator)
        self._ledger.log_fill(
            order_id=order.id,
            symbol=order.pair,
            side=order.side,
            price=order.price,
            quantity=order.quantity,
            strategy=order.strategy,
        )
        self._ledger.log_process_event(
            order.id, "order_filled", operator,
            {"price": order.price, "quantity": order.quantity, "auto": order.auto_approved},
        )

    def _signal(self, order_id: str) -> None:
        event = self._events.get(order_id)
        if event is not None:
            event.set()


def make_approval_handler(store: OrderStore) -> Callable[[Dict[str, Any]], Any]:
    """Build an orchestrator ``approval_handler`` backed by ``store``.

    The orchestrator passes its signal dict; we register a pending order and
    block until a human resolves it via the API.
    """

    async def handler(signal: Dict[str, Any]) -> bool:
        order = Order(
            pair=signal.get("symbol", "UNKNOWN"),
            side=signal.get("action", "buy").lower(),
            quantity=float(signal.get("quantity", 0.0)) or 0.0,
            price=float(signal.get("entry_price", 0.0)) or 0.0,
            strategy=signal.get("strategy", "unknown"),
            agent_id=signal.get("agent_id", "strategy_agent"),
            confidence=float(signal.get("confidence", 0.0)) or 0.0,
            reason=signal.get("reason", "n/a"),
            critical=bool(signal.get("critical", False)),
        )
        store.submit(order)
        if order.status == OrderStatus.filled:  # auto-approved
            return True
        return await store.wait_for_decision(order.id)

    return handler


__all__ = ["Order", "OrderStatus", "OrderStore", "OrderConflictError", "make_approval_handler"]
