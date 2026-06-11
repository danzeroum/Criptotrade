"""HITL order bridge — SQLite-backed, cross-process (Phase 5a-ii).

Lifecycle::

    pending ──auto (≤ threshold, not critical)──► filled        (local ledger fill)
       │
       ├──approve (human, API)──► approved ──loop executes──► filled
       │
       └──reject──► rejected            cancelled (timeout)

Cross-process model: the **API decides** (writes ``approved``/``rejected`` to the
shared SQLite ``orders`` table) and the **loop executes** (sees ``approved`` via
``wait_for_decision`` polling, runs the execution agent, then calls
:meth:`OrderStore.mark_filled`). Auto-approval (Model B) fills locally on submit —
it is a system-trusted small order recorded straight to the ledger.

State lives in SQLite (WAL) so the two processes share it; the audit trail (XES
process events, fills, HITL approvals) still goes to the JSONL ledger in 5a.
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from src.core.db import connection, init_db
from src.core.ledger import TradingLedger
from src.safety.guardrails import GuardrailSystem


class OrderStatus(str, Enum):
    pending = "pending"
    approved = "approved"  # human-approved, awaiting loop execution (cross-process)
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
    position_size_pct: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
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

    def guardrail_view(self) -> Dict[str, Any]:
        """Project the order into the dict shape GuardrailSystem expects."""
        return {
            "position_size_pct": self.position_size_pct,
            "action": self.side.upper(),
            "entry_price": self.price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
        }

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


_COLUMNS = (
    "id", "pair", "side", "quantity", "price", "strategy", "agent_id", "confidence",
    "reason", "critical", "position_size_pct", "stop_loss", "take_profit", "status",
    "operator_note", "operator_id", "auto_approved", "created_at", "resolved_at", "filled_at",
)


def _row_to_order(row: Any) -> Order:
    return Order(
        pair=row["pair"], side=row["side"], quantity=row["quantity"], price=row["price"],
        strategy=row["strategy"], agent_id=row["agent_id"], confidence=row["confidence"],
        reason=row["reason"], critical=bool(row["critical"]),
        position_size_pct=row["position_size_pct"] or 0.0,
        stop_loss=row["stop_loss"], take_profit=row["take_profit"],
        # TODO(5b): position_size_pct uses `or 0.0` while stop_loss/take_profit
        # preserve None — small semantic inconsistency, normalise in 5b.
        status=OrderStatus(row["status"]), operator_note=row["operator_note"],
        operator_id=row["operator_id"], auto_approved=bool(row["auto_approved"]),
        id=row["id"], created_at=row["created_at"], resolved_at=row["resolved_at"],
        filled_at=row["filled_at"],
    )


class OrderStore:
    """SQLite-backed order store shared across the API and the loop processes."""

    def __init__(
        self,
        ledger: TradingLedger,
        threshold_provider: Callable[[], float],
        decision_timeout: float = 300.0,
        guardrails: Optional[GuardrailSystem] = None,
        db_path: Optional[str] = None,
        poll_interval: float = 2.0,
    ) -> None:
        self._ledger = ledger
        self._threshold_provider = threshold_provider
        # Pending orders with no decision within this window are auto-cancelled.
        self._decision_timeout = decision_timeout
        # When set, every order is risk-validated BEFORE any approval decision.
        self._guardrails = guardrails
        self._db_path = db_path
        self._poll_interval = poll_interval
        init_db(db_path)  # idempotent: ensure the schema exists

    # ------------------------------------------------------------------ submit
    def submit(self, order: Order) -> Order:
        """Persist an order; risk-validate, then auto-fill or leave pending."""
        self._insert(order)
        self._ledger.log_process_event(
            order.id, "order_submitted", order.agent_id,
            {"pair": order.pair, "side": order.side, "notional": order.notional},
        )

        # Risk gate FIRST: thresholds are value-based; guardrails are risk-based.
        if self._guardrails is not None and not self._risk_ok(order):
            return order

        threshold = self._threshold_provider()
        auto = (threshold > 0) and (order.notional <= threshold) and not order.critical
        if auto:
            # Model B: auto-approval fills locally (system-trusted small order).
            order.auto_approved = True
            self._do_fill(order, operator="auto")
        return order

    def _risk_ok(self, order: Order) -> bool:
        """Run guardrails; reject the order on violation. Returns True if it passed."""
        try:
            passed, violations = self._guardrails.validate_order(order.guardrail_view())
        except Exception as exc:  # defensive: any failure -> rejected, never raise
            passed, violations = False, [f"risk validation error: {exc}"]
        if passed:
            return True
        order.status = OrderStatus.rejected
        order.resolved_at = _now()
        order.operator_note = "; ".join(violations) or "risk validation failed"
        self._update(order)
        self._ledger.log_hitl_approval(approved=False, order=order.to_dict(), user="guardrails")
        self._ledger.log_process_event(order.id, "order_rejected", "guardrails", {"violations": violations})
        return False

    # ------------------------------------------------------------------ resolve
    def resolve(
        self,
        order_id: str,
        approved: bool,
        operator: str = "operator",
        operator_note: Optional[str] = None,
    ) -> Order:
        """Human decision on a pending order. Approve -> ``approved`` (the loop
        fills); reject -> ``rejected``. Raises if it is not pending."""
        order = self.get(order_id)
        if order is None:
            raise KeyError(order_id)
        if order.status != OrderStatus.pending:
            raise OrderConflictError(order)

        order.operator_id = operator
        order.operator_note = operator_note
        order.resolved_at = _now()
        if approved:
            order.status = OrderStatus.approved
            self._update(order)
            self._ledger.log_hitl_approval(approved=True, order=order.to_dict(), user=operator)
            self._ledger.log_process_event(order.id, "order_approved", operator, {})
        else:
            order.status = OrderStatus.rejected
            self._update(order)
            self._ledger.log_hitl_approval(approved=False, order=order.to_dict(), user=operator)
            self._ledger.log_process_event(order.id, "order_rejected", operator, {"note": operator_note})
        return order

    def mark_filled(self, order_id: str, operator: str = "loop") -> Optional[Order]:
        """Transition ``approved`` -> ``filled`` (loop calls this post-execution).

        The ``WHERE status='approved'`` guard makes it atomic and idempotent: it
        never fills an order that wasn't approved (no silent double-fill).
        """
        now = _now()
        with connection(self._db_path) as conn:
            cur = conn.execute(
                "UPDATE orders SET status='filled', filled_at=?, "
                "resolved_at=COALESCE(resolved_at, ?) WHERE id=? AND status='approved'",
                (now, now, order_id),
            )
            affected = cur.rowcount
        order = self.get(order_id)
        if affected and order is not None:
            self._log_fill_events(order, operator)
        return order

    def cancel(self, order_id: str, reason: str = "timeout") -> Optional[Order]:
        """Cancel a pending order (e.g. on decision timeout). Idempotent."""
        order = self.get(order_id)
        if order is None or order.status != OrderStatus.pending:
            return order
        order.status = OrderStatus.cancelled
        order.resolved_at = _now()
        order.operator_note = reason
        self._update(order)
        self._ledger.log_process_event(order.id, "order_cancelled", "system", {"reason": reason})
        return order

    # ------------------------------------------------------------------ queries
    def get(self, order_id: str) -> Optional[Order]:
        with connection(self._db_path) as conn:
            row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        return _row_to_order(row) if row else None

    def list(
        self,
        status: Optional[OrderStatus] = None,
        pair: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Order]:
        query = "SELECT * FROM orders"
        clauses: List[str] = []
        params: List[Any] = []
        if status is not None:
            clauses.append("status=?")
            params.append(status.value)
        if pair is not None:
            clauses.append("pair=?")
            params.append(pair)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
            if offset:
                query += " OFFSET ?"
                params.append(offset)
        with connection(self._db_path) as conn:
            rows = conn.execute(query, params).fetchall()
        return [_row_to_order(r) for r in rows]

    def count(
        self,
        status: Optional[OrderStatus] = None,
        pair: Optional[str] = None,
    ) -> int:
        """Return total matching orders (ignoring pagination) for Meta.total."""
        query = "SELECT COUNT(*) FROM orders"
        clauses: List[str] = []
        params: List[Any] = []
        if status is not None:
            clauses.append("status=?")
            params.append(status.value)
        if pair is not None:
            clauses.append("pair=?")
            params.append(pair)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        with connection(self._db_path) as conn:
            return conn.execute(query, params).fetchone()[0]

    def pending_count(self) -> int:
        with connection(self._db_path) as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM orders WHERE status='pending'"
            ).fetchone()[0]

    # ------------------------------------------------------------------ bridge
    async def wait_for_decision(self, order_id: str, timeout: Optional[float] = None) -> bool:
        """Poll the shared ``status`` until decided (cross-process).

        Returns ``True`` if ``approved``/``filled``, ``False`` if
        ``rejected``/``cancelled`` or on timeout (fail-closed: a stuck approval is
        auto-cancelled and never blocks the loop forever).
        """
        timeout = self._decision_timeout if timeout is None else timeout
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with connection(self._db_path) as conn:
                row = conn.execute(
                    "SELECT status FROM orders WHERE id=?", (order_id,)
                ).fetchone()
            # TODO(5b): a non-existent order_id currently waits out the whole
            # timeout. Return False immediately on `row is None` instead.
            if row is not None:
                status = row["status"]
                if status in ("approved", "filled"):
                    return True
                if status in ("rejected", "cancelled"):
                    return False
            await asyncio.sleep(self._poll_interval)
        self.cancel(order_id, reason="decision_timeout")
        return False

    # ------------------------------------------------------------------ helpers
    def _insert(self, order: Order) -> None:
        placeholders = ",".join("?" for _ in _COLUMNS)
        values = (
            order.id, order.pair, order.side, order.quantity, order.price, order.strategy,
            order.agent_id, order.confidence, order.reason, int(order.critical),
            order.position_size_pct, order.stop_loss, order.take_profit, order.status.value,
            order.operator_note, order.operator_id, int(order.auto_approved),
            order.created_at, order.resolved_at, order.filled_at,
        )
        with connection(self._db_path) as conn:
            conn.execute(f"INSERT INTO orders ({','.join(_COLUMNS)}) VALUES ({placeholders})", values)

    def _update(self, order: Order) -> None:
        with connection(self._db_path) as conn:
            conn.execute(
                "UPDATE orders SET status=?, operator_note=?, operator_id=?, auto_approved=?, "
                "resolved_at=?, filled_at=? WHERE id=?",
                (order.status.value, order.operator_note, order.operator_id,
                 int(order.auto_approved), order.resolved_at, order.filled_at, order.id),
            )

    def _do_fill(self, order: Order, operator: str) -> None:
        """Fill straight from the in-memory object (auto-approval path)."""
        order.status = OrderStatus.filled
        order.resolved_at = _now()
        order.filled_at = order.resolved_at
        self._update(order)
        self._log_fill_events(order, operator)

    def _log_fill_events(self, order: Order, operator: str) -> None:
        self._ledger.log_hitl_approval(approved=True, order=order.to_dict(), user=operator)
        self._ledger.log_fill(
            order_id=order.id, symbol=order.pair, side=order.side,
            price=order.price, quantity=order.quantity, strategy=order.strategy,
        )
        self._ledger.log_process_event(
            order.id, "order_filled", operator,
            {"price": order.price, "quantity": order.quantity, "auto": order.auto_approved},
        )


def make_approval_handler(store: OrderStore) -> Callable[[Dict[str, Any]], Any]:
    """Build an orchestrator ``approval_handler`` backed by ``store``.

    Returns the **order id** (truthy) when the order is approved/filled, or
    ``None`` when rejected/cancelled/unsized. The orchestrator coerces the result
    to a bool for the approve/deny decision *and* keeps the id so it can call
    ``mark_filled`` once it has executed the trade (completing the manual path).
    """

    async def handler(signal: Dict[str, Any]) -> Optional[str]:
        price = float(signal.get("entry_price", 0.0)) or 0.0
        size_pct = float(signal.get("position_size_pct", 0.0)) or 0.0
        quantity = float(signal.get("quantity", 0.0)) or 0.0
        if quantity <= 0 and price > 0 and size_pct > 0:
            # Demo signals carry position_size_pct, not an absolute quantity:
            # derive qty = capital * size_pct% / price (same basis as the ledger fill).
            capital = float(os.getenv("INITIAL_CAPITAL", "10000"))
            quantity = (capital * size_pct / 100.0) / price
        if quantity <= 0 or price <= 0:
            # Can't size the order -> fail-closed (never INSERT an invalid order).
            return None
        order = Order(
            pair=signal.get("symbol", "UNKNOWN"),
            side=signal.get("action", "buy").lower(),
            quantity=quantity,
            price=price,
            strategy=signal.get("strategy", "unknown"),
            agent_id=signal.get("agent_id", "strategy_agent"),
            confidence=float(signal.get("confidence", 0.0)) or 0.0,
            reason=signal.get("reason", "n/a"),
            critical=bool(signal.get("critical", False)),
            position_size_pct=size_pct,
            stop_loss=signal.get("stop_loss"),
            take_profit=signal.get("take_profit"),
        )
        store.submit(order)
        if order.status == OrderStatus.filled:  # auto-approved
            return order.id
        if order.status in (OrderStatus.rejected, OrderStatus.cancelled):
            return None
        approved = await store.wait_for_decision(order.id)
        return order.id if approved else None

    return handler


__all__ = ["Order", "OrderStatus", "OrderStore", "OrderConflictError", "make_approval_handler"]
