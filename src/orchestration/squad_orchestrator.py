"""Orchestrator for multi-agent trading operations."""
from __future__ import annotations

import logging
import os
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from src.agents.execution_agent import ExecutionAgent
from src.agents.risk_agent import RiskAgent
from src.agents.strategy_agent import StrategyAgent
from src.core.alerts import Alert, AlertBus, AlertStore
from src.core.ledger import TradingLedger
from src.orchestration.position_store import PositionStore

logger = logging.getLogger(__name__)

# Quantity tolerance for FIFO fill matching: lots within EPS of each other are
# considered equal (real lot sizes are ~1e-3 BTC, so 1e-9 is pure float noise).
EPS = 1e-9


class CircuitBreaker:
    """Pause trading when daily loss or consecutive losses exceed limits.

    Thresholds from risk_params.yaml:
      trigger_daily_loss_pct: 4.0
      trigger_consecutive_losses: 3
      cooldown_period_hours: 24
    """

    DAILY_LOSS_LIMIT_PCT: float = 4.0
    CONSECUTIVE_LOSS_LIMIT: int = 3
    COOLDOWN_SECONDS: float = 24 * 3600

    def __init__(
        self,
        ledger: TradingLedger | None = None,
        state_db_provider: Callable[[], Any] | None = None,
    ) -> None:
        self._ledger = ledger
        self._tripped_at: float | None = None
        self._consecutive_losses: int = 0
        self._daily_loss_pct: float = 0.0
        # Optional SQLite persistence so the breaker survives a loop restart.
        # None = in-memory only (default; behaviour unchanged).
        self._state_db = state_db_provider

    def reload(self) -> None:
        """Restore persisted breaker state (no-op when persistence is disabled)."""
        if self._state_db is None:
            return
        from src.orchestration.position_store import load_circuit_state

        state = load_circuit_state(self._state_db)
        if state:
            self._tripped_at = state["tripped_at"]
            self._consecutive_losses = int(state["consecutive_losses"])
            self._daily_loss_pct = float(state["daily_loss_pct"])

    def _persist(self) -> None:
        if self._state_db is None:
            return
        from src.orchestration.position_store import save_circuit_state

        save_circuit_state(
            self._state_db, self._tripped_at, self._consecutive_losses, self._daily_loss_pct
        )

    @property
    def is_open(self) -> bool:
        """True = circuit is OPEN (trading blocked)."""
        if self._tripped_at is None:
            return False
        elapsed = time.time() - self._tripped_at
        if elapsed >= self.COOLDOWN_SECONDS:
            self._reset("cooldown expired")
            return False
        return True

    def record_trade_result(self, pnl_pct: float) -> None:
        """Update internal counters after a trade completes."""
        self._daily_loss_pct += pnl_pct

        if pnl_pct < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

        if self._daily_loss_pct <= -self.DAILY_LOSS_LIMIT_PCT:
            self._trip(
                f"daily loss {self._daily_loss_pct:.2f}% reached -{self.DAILY_LOSS_LIMIT_PCT}%"
            )
        elif self._consecutive_losses >= self.CONSECUTIVE_LOSS_LIMIT:
            self._trip(
                f"{self._consecutive_losses} consecutive losses"
                f" reached limit {self.CONSECUTIVE_LOSS_LIMIT}"
            )
        self._persist()

    def reset_daily(self) -> None:
        """Call once per trading day to reset the daily loss counter."""
        self._daily_loss_pct = 0.0
        if self._tripped_at is not None:
            elapsed = time.time() - self._tripped_at
            if elapsed >= self.COOLDOWN_SECONDS:
                self._reset("daily reset")
        self._persist()

    def _trip(self, reason: str) -> None:
        if self._tripped_at is not None:
            return  # already tripped
        self._tripped_at = time.time()
        msg = f"Circuit breaker TRIPPED: {reason}. Cooldown {self.COOLDOWN_SECONDS/3600:.0f}h."
        logger.critical(msg)
        if self._ledger is not None:
            try:
                self._ledger.log_decision("circuit_breaker_tripped", {"reason": reason})
            except Exception:
                pass

    def _reset(self, reason: str) -> None:
        self._tripped_at = None
        self._consecutive_losses = 0
        logger.info("Circuit breaker RESET: %s.", reason)
        if self._ledger is not None:
            try:
                self._ledger.log_decision("circuit_breaker_reset", {"reason": reason})
            except Exception:
                pass
        self._persist()


class SquadOrchestrator:
    """Coordinates strategy, risk, and execution agents."""

    def __init__(
        self,
        exchange_client: Any,
        approval_handler: Callable[[dict[str, Any]], Awaitable[bool]] | None = None,
        initial_capital: float = 10_000.0,
        alert_store: AlertStore | None = None,
        alert_bus: AlertBus | None = None,
        fill_callback: Callable[[str], Any] | None = None,
    ) -> None:
        self.strategy_agent = StrategyAgent(exchange_client=exchange_client)
        self.risk_agent = RiskAgent()
        self.execution_agent = ExecutionAgent(exchange_client)
        self.ledger = TradingLedger()
        self.circuit_breaker = CircuitBreaker(
            ledger=self.ledger, state_db_provider=lambda: self.ledger.db_path
        )
        # Real HITL hook. When None, approvals are denied (fail-closed).
        self.approval_handler = approval_handler
        # Used to size paper fills (qty = capital * position_size_pct / price).
        self.initial_capital = initial_capital
        # Optional alert sink. When provided, risk rejections emit guardrail alerts.
        self.alert_store = alert_store
        self.alert_bus = alert_bus
        # Called with the approved order id after a successful execution, so the
        # OrderStore order completes approved -> filled (the manual HITL path).
        self.fill_callback = fill_callback
        self._last_order_ref: str | None = None
        # Paper position book: tracks open fills so stop/TP exits can be logged.
        self._open_positions: dict[str, dict[str, Any]] = {}
        # SQLite mirror so the book survives a loop restart (no zombie positions).
        self._positions = PositionStore(lambda: self.ledger.db_path)
        # N3: N pairs compete for MAX_CONCURRENT_POSITIONS slots — opening a new
        # lot when full is skipped (no_slot). Read fresh from env so tests and the
        # loop pick up the deployment's value.
        self._max_concurrent = max(1, int(os.getenv("MAX_CONCURRENT_POSITIONS", "3") or 3))
        # N3: last skip reason per symbol, so we log STATE TRANSITIONS (+ a throttled
        # heartbeat) instead of one event per cycle — the ledger/A4 don't drown.
        self._last_skip: dict[str, dict[str, Any]] = {}
        # Wire the RiskAgent's guardrails to publish each violation as an alert.
        if alert_store is not None:
            from src.core.alerts import make_guardrail_sink

            self.risk_agent.guardrails.alert_sink = make_guardrail_sink(alert_store)

    async def _request_human_approval(self, order: dict[str, Any]) -> bool:
        """Request real human approval. Fail-closed: deny when no handler is configured."""
        if self.approval_handler is None:
            self._last_order_ref = None
            logger.warning("No HITL approval handler configured; denying trade (fail-closed)")
            return False
        result = await self.approval_handler(order)
        # The OrderStore bridge returns the order id (str) on approval; other
        # handlers return a bool. Keep the id to mark_filled post-execution.
        self._last_order_ref = result if isinstance(result, str) else None
        return bool(result)

    def reload_open_positions(self) -> None:
        """Restore the paper position book + breaker state from SQLite.

        Call once at loop startup so a restart doesn't strand open positions
        (they'd otherwise never be closed at stop/TP — "zombie" positions) or
        forget a loss streak in the circuit breaker.
        """
        restored = self._positions.load_all()
        if restored:
            self._open_positions = restored
            logger.info("Restored %d open paper position(s) from disk", len(restored))
        self.circuit_breaker.reload()

    # Re-emit a persistent skip at most this often (with a running count), so a
    # symbol stuck on "confidence_low" produces ~1 event / 10 min, not 1 / cycle.
    _SKIP_THROTTLE_S = 600.0

    def _record_skip(
        self,
        symbol: str,
        reason: str,
        extra: dict[str, Any] | None = None,
        heartbeat: bool = True,
    ) -> None:
        """Book a ``signal_skipped`` event — on a reason CHANGE (or first time), or a
        throttled heartbeat while the reason persists. Feeds the N3 feed + A4.

        ``heartbeat=False`` (N9 pause): emit ONLY on the transition, never re-emit
        while the reason persists. Pause is a deliberate config state, not a
        transient contest like ``no_slot``/``circuit_breaker`` — a pair paused for a
        month must not spam the ledger; its steady state is visible via
        ``config_changed`` and the ``paused`` badge instead."""
        now = time.time()
        prev = self._last_skip.get(symbol)
        if prev and prev["reason"] == reason:
            prev["count"] += 1
            if not heartbeat or now - prev["last_emit"] < self._SKIP_THROTTLE_S:
                return  # same reason, within the window (or no heartbeat) — stay quiet
            prev["last_emit"] = now
            count, since = prev["count"], prev["since"]
        else:
            self._last_skip[symbol] = {"reason": reason, "count": 1, "since": now, "last_emit": now}
            count, since = 1, now
        data: dict[str, Any] = {
            "symbol": symbol, "reason": reason, "count": count,
            "since": datetime.fromtimestamp(since, tz=UTC).isoformat(),
        }
        if extra:
            data.update(extra)
        try:
            self.ledger.log_decision("signal_skipped", data)
        except Exception:  # pragma: no cover - a skip log must never break the loop
            logger.warning("Failed to log signal_skipped for %s", symbol, exc_info=True)

    def _clear_skip(self, symbol: str) -> None:
        """A symbol that traded resets its skip state (next skip is a fresh transition)."""
        self._last_skip.pop(symbol, None)

    @staticmethod
    def _risk_skip_reason(issues: list[Any]) -> str:
        """Map a RiskAgent rejection to a skip reason for the feed."""
        joined = " ".join(str(i) for i in issues).lower()
        if "insufficient capital" in joined:
            return "insufficient_capital"
        return "risk_rejected"

    async def analyze_and_trade(
        self, symbol: str, timeframe: str = "1h", *, paused: bool = False
    ) -> dict[str, Any]:
        """Full trading pipeline with agent collaboration.

        ``paused`` (N9) is resolved by the loop each cycle from the ``operated_pairs``
        table. A paused pair still has its open positions managed (stop/TP), but the
        loop skips opening NEW orders for it — the gate sits after the position check
        and before the new-order pipeline."""
        if self.circuit_breaker.is_open:
            logger.warning("Circuit breaker is OPEN — skipping trade cycle for %s", symbol)
            self._record_skip(symbol, "circuit_breaker")
            return {
                "success": False,
                "reason": "Circuit breaker active — trading paused",
            }

        logger.info("Starting analysis", extra={"symbol": symbol, "timeframe": timeframe})

        strategy_result = await self.strategy_agent.execute({
            "symbol": symbol,
            "timeframe": timeframe,
        })

        # Ensure the signal carries the symbol so the order records the real pair
        # (the demo strategy stub omits it) — fixes orders showing pair="UNKNOWN".
        strategy_result["signal"].setdefault("symbol", symbol)

        # Surface a silent data fallback: trading on synthetic stub data (e.g. a
        # failed live OHLCV fetch) must not pass unnoticed by the operator.
        if strategy_result.get("stub_used"):
            await self._emit_stub_alert(symbol)

        # Check open paper positions against current price on every cycle, even
        # when this cycle generates no new trade (fail-safe: wrap so a close error
        # never blocks the trading pipeline).
        current_price = float(strategy_result["signal"].get("entry_price") or 0.0)
        if current_price > 0:
            try:
                self._check_open_positions(current_price, symbol)
            except Exception:
                logger.warning("Position check failed for %s", symbol, exc_info=True)

        # N9: a paused pair keeps its positions managed above, but opens no new
        # order. Gate here — after the stop/TP check, before the new-order pipeline.
        # Transition-only skip (no heartbeat): pause is a persistent config state.
        if paused:
            logger.info("Pair %s is paused — skipping new orders (positions still managed)", symbol)
            self._record_skip(symbol, "paused", heartbeat=False)
            return {"success": False, "reason": "paused"}

        self.ledger.log_signal(
            agent="strategy", signal=strategy_result["signal"],
            confidence=strategy_result.get("confidence"),
        )

        if strategy_result["confidence"] < 0.6:
            logger.info("Signal confidence too low, skipping")
            self._record_skip(symbol, "confidence_low",
                              {"confidence": strategy_result["confidence"]})
            return {
                "success": False,
                "reason": "Low confidence signal",
                "confidence": strategy_result["confidence"],
            }

        risk_result = await self.risk_agent.execute({
            "signal": strategy_result["signal"],
            "portfolio": {
                "available_capital": self._available_capital(),
                "capital_base": self.initial_capital,
            },
        })

        self.ledger.log_validation(agent="risk", validation=risk_result["validation"])

        if not risk_result["approved"]:
            issues = risk_result["validation"]["issues"]
            logger.warning("Signal rejected by Risk Agent", extra={"issues": issues})
            await self._emit_alert(symbol, issues)
            self._record_skip(symbol, self._risk_skip_reason(issues), {"issues": issues})
            return {
                "success": False,
                "reason": "Risk validation failed",
                "issues": issues,
            }

        # Spot semantics (ALLOW_SHORTS=false, hardcoded — a futures/margin flag is
        # declared backlog): a SELL only sells existing long inventory; it never
        # opens a naked short (a real spot SELL with no balance is rejected). A fill
        # that REDUCES an opposite-side open lot is "closing" (frees a slot); net-new
        # exposure competes for the bounded book (N3 slot cap). The old gate keyed
        # the cap bypass on symbol-only + sell-only, so a SELL with only shorts open
        # bypassed the cap and _match_or_open opened yet another short — unbounded
        # short accumulation. Keying on the OPPOSITE-side lot fixes that at the root.
        action = str(strategy_result["signal"].get("action", "buy")).lower()
        opposite_side = "buy" if action == "sell" else "sell"
        opposite_qty = sum(
            float(p.get("quantity") or 0.0)
            for p in self._open_positions.values()
            if p.get("symbol") == symbol and p.get("side") == opposite_side
        )
        is_closing = opposite_qty > EPS

        if action == "sell" and not is_closing:
            # No long inventory to sell → skip (spot: never short). Transition-only.
            logger.info("No long inventory to sell for %s — skipping (spot: no naked short)", symbol)
            self._record_skip(symbol, "no_inventory", heartbeat=False)
            return {"success": False, "reason": "no_inventory"}

        # N3 slot cap: new exposure competes for a bounded book; a closing fill frees a slot.
        if len(self._open_positions) >= self._max_concurrent and not is_closing:
            logger.info("No free position slot (%d/%d) — skipping %s",
                        len(self._open_positions), self._max_concurrent, symbol)
            self._record_skip(symbol, "no_slot", {"slots_open": len(self._open_positions)})
            return {
                "success": False,
                "reason": "No free position slot",
                "slots_open": len(self._open_positions),
            }

        logger.info("⏸️  HITL approval required")
        human_approved = await self._request_human_approval(strategy_result["signal"])

        self.ledger.log_hitl_approval(approved=human_approved, order=strategy_result["signal"])

        if not human_approved:
            return {
                "success": False,
                "reason": "Human rejected the trade",
            }

        execution_result = await self.execution_agent.execute({
            "signal": strategy_result["signal"],
            "human_approved": human_approved,
            # Size here so the execution agent can place a real paper order
            # (slippage + fee applied) instead of fabricating a fill.
            "quantity": self._position_quantity(strategy_result["signal"]),
        })

        self.ledger.log_execution(agent="execution", execution=execution_result)

        if execution_result.get("success"):
            self._log_fill(symbol, strategy_result["signal"], execution_result)
            self._clear_skip(symbol)  # traded → reset skip state (next skip is fresh)
            # Complete the manual HITL path: approved -> filled in the OrderStore.
            # No-op for auto-filled orders (mark_filled guards on status='approved').
            if self.fill_callback is not None and self._last_order_ref is not None:
                try:
                    self.fill_callback(self._last_order_ref)
                except Exception:  # pragma: no cover - never break a completed trade
                    logger.warning(
                        "fill_callback failed for %s", self._last_order_ref, exc_info=True
                    )

        # Reset so a stale ref from this cycle can never leak into the next; the
        # next cycle sets it fresh when it submits an order.
        self._last_order_ref = None
        return {
            "success": execution_result["success"],
            "order_id": execution_result.get("order_id"),
            "signal": strategy_result["signal"],
            "confidence": strategy_result["confidence"],
        }

    def _realized_pnl(self) -> float:
        """Sum realised P&L from closed paper positions in the ledger."""
        total = 0.0
        try:
            for entry in self.ledger.get_events("position_closed"):
                data = entry.get("data") or {}
                try:
                    total += float(data.get("pnl") or 0.0)
                except (TypeError, ValueError):
                    continue
        except Exception:  # pragma: no cover - defensive (ledger read)
            logger.warning("Could not read realised P&L", exc_info=True)
        return total

    def _available_capital(self) -> float:
        """Capital available for a new position: base + realised − open exposure."""
        open_notional = sum(
            float(p.get("entry_price", 0) or 0) * float(p.get("quantity", 0) or 0)
            for p in self._open_positions.values()
        )
        return self.initial_capital + self._realized_pnl() - open_notional

    def _position_quantity(self, signal: dict[str, Any]) -> float:
        """Quantity for a paper fill: ``capital * position_size_pct / entry price``.

        Sizing uses the signal's intended entry price (the market order then
        fills at a slipped price). A malformed signal yields ``0`` so the caller
        skips it rather than crashing a trade that already executed.
        """
        try:
            price = float(signal.get("entry_price") or 0.0)
            size_pct = float(signal.get("position_size_pct") or 0.0)
        except (TypeError, ValueError):
            return 0.0
        if price <= 0 or size_pct <= 0:
            return 0.0
        return (self.initial_capital * size_pct / 100.0) / price

    def _log_fill(self, symbol: str, signal: dict[str, Any], execution: dict[str, Any]) -> None:
        """Record the economic facts of a fill so metrics can value the position.

        Prefers the exchange's **executed price + fee** (slippage/fee applied)
        for honest paper P&L, falling back to the signal's entry price for test
        doubles that return a bare order. Best-effort: a malformed signal must
        not break the trade that already executed.
        """
        try:
            quantity = self._position_quantity(signal)
            if quantity <= 0:
                return
            signal_price = float(signal.get("entry_price") or 0.0)
            executed = execution.get("executed_price")
            price = float(executed) if executed else signal_price
            fee = float(execution.get("fee") or 0.0)
            if price <= 0:
                return
            order_id = execution.get("order_id", "UNKNOWN")
            self.ledger.log_fill(
                order_id=order_id,
                symbol=signal.get("symbol", symbol),
                side=signal.get("action", "buy"),
                price=price,
                quantity=quantity,
                fee=fee,
            )
            # FIFO grid accounting: an opposite-side fill nets against open
            # inventory (closing lots, realising P&L) before any residue opens
            # a new position. Entry basis is the executed price so realised P&L
            # reflects entry slippage.
            sl = signal.get("stop_loss")
            tp = signal.get("take_profit")
            self._match_or_open(
                symbol=signal.get("symbol", symbol),
                side=signal.get("action", "buy").lower(),
                price=price,
                quantity=quantity,
                fee=fee,
                order_id=order_id,
                stop_loss=float(sl) if sl is not None else None,
                take_profit=float(tp) if tp is not None else None,
            )
        except (TypeError, ValueError):  # pragma: no cover - defensive
            logger.warning("Could not record fill for %s", symbol, exc_info=True)

    def _match_or_open(
        self,
        symbol: str,
        side: str,
        price: float,
        quantity: float,
        fee: float,
        order_id: str,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> None:
        """Net a fill against open opposite-side lots (FIFO), then open any residue.

        Grid semantics: a SELL closes the oldest open BUY lots of the same symbol
        (and vice-versa), realising P&L per matched chunk with pro-rata fees from
        both sides. Quantity left after netting opens a new position under this
        fill's ``order_id``. With no opposite lot the whole fill opens — identical
        to the pre-matching behaviour for an isolated buy or sell.
        """
        opposite = "sell" if side == "buy" else "buy"
        candidates = [
            (oid, p)
            for oid, p in self._open_positions.items()
            if p["symbol"] == symbol and p["side"] == opposite
        ]
        # FIFO: oldest lot first (stable sort keeps insertion order on ties).
        candidates.sort(key=lambda kv: kv[1].get("opened_at") or "")

        # Plan the FIFO matches first so the leftover (residual) is known before the
        # closes are booked — the residual is attached to the FINAL close event.
        plan: list[tuple[str, dict[str, Any], float, bool]] = []
        remaining = quantity
        for oid, pos in candidates:
            if remaining <= EPS:
                break
            pos_qty = float(pos["quantity"])
            matched = min(remaining, pos_qty)
            plan.append((oid, pos, matched, matched >= pos_qty - EPS))
            remaining -= matched
        residual = remaining if remaining > EPS else 0.0
        # Spot: a SELL never opens a short — the residual beyond netted inventory is
        # dropped and audited (on the last close). A BUY residual opens a long.
        drop_on_close = residual if (side == "sell" and residual > EPS) else None

        for i, (oid, pos, matched, is_full) in enumerate(plan):
            pos_qty = float(pos["quantity"])
            exit_fee_chunk = fee * (matched / quantity) if quantity else 0.0
            entry_fee_chunk = (
                float(pos.get("entry_fee", 0.0)) * (matched / pos_qty) if pos_qty else 0.0
            )
            residual_arg = drop_on_close if i == len(plan) - 1 else None
            if is_full:  # full close of this lot
                self._record_close(
                    oid, pos, exit_price=price,
                    exit_fee=exit_fee_chunk, entry_fee=entry_fee_chunk,
                    closed_qty=pos_qty, residual_dropped=residual_arg,
                )
            else:  # partial: book the chunk, shrink the lot in place
                self._record_close(
                    oid, pos, exit_price=price,
                    exit_fee=exit_fee_chunk, entry_fee=entry_fee_chunk,
                    closed_qty=matched, keep_open=True, residual_dropped=residual_arg,
                )
                pos["quantity"] = pos_qty - matched
                pos["entry_fee"] = float(pos.get("entry_fee", 0.0)) * (pos["quantity"] / pos_qty)
                self._positions.upsert(oid, pos)

        if residual > EPS:
            if side == "buy":  # net-new long — holding spot inventory is legitimate
                new_pos = {
                    "symbol": symbol,
                    "side": side,
                    "entry_price": price,
                    "quantity": residual,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "entry_fee": fee * (residual / quantity) if quantity else 0.0,
                    "opened_at": datetime.now(UTC).isoformat(),
                }
                self._open_positions[order_id] = new_pos
                self._positions.upsert(order_id, new_pos)
            else:  # spot: drop the unsellable SELL residual — never open a short
                logger.info("Dropped unsellable SELL residual %.8f %s (spot: no naked short)",
                            residual, symbol)
                if not plan:  # nothing to net (defensive: the gate blocks this path)
                    self.ledger.log_decision(
                        "sell_residual_dropped",
                        {"symbol": symbol, "order_id": order_id, "quantity": residual,
                         "reason": "no_inventory"},
                    )

    def _check_open_positions(self, current_price: float, symbol: str) -> None:
        """Close any paper positions whose stop-loss or take-profit has been reached.

        Called once per cycle, before deciding on a new trade. Writes a
        ``position_closed`` ledger event and feeds the circuit breaker for each
        exit so Kelly / consecutive-loss counters stay accurate.
        """
        to_close = [
            (oid, pos)
            for oid, pos in list(self._open_positions.items())
            if pos["symbol"] == symbol and self._exit_price(pos, current_price) is not None
        ]
        for oid, pos in to_close:
            exit_price = self._exit_price(pos, current_price)
            self._record_close(oid, pos, exit_price)

    def _record_close(
        self,
        oid: str,
        pos: dict[str, Any],
        exit_price: float,
        exit_fee: float = 0.0,
        entry_fee: float = 0.0,
        closed_qty: float | None = None,
        keep_open: bool = False,
        residual_dropped: float | None = None,
    ) -> None:
        """Book a position close: ledger event + circuit-breaker feed.

        Single close path shared by stop/TP exits and (future) fill matching, so
        P&L accounting and breaker feeding cannot diverge. ``closed_qty`` allows
        partial closes; ``keep_open=True`` books the chunk without removing the
        (shrunken) lot from the position book. ``residual_dropped`` records a SELL
        quantity discarded rather than opened as a naked short (spot). Feeds the
        breaker exactly once.
        """
        qty = closed_qty if closed_qty is not None else pos["quantity"]
        if not keep_open:
            self._open_positions.pop(oid, None)
            self._positions.delete(oid)
        fee = entry_fee + exit_fee
        self.ledger.log_position_closed(
            order_id=oid,
            symbol=pos["symbol"],
            side=pos["side"],
            entry_price=pos["entry_price"],
            exit_price=exit_price,
            quantity=qty,
            fee=fee,
            opened_at=pos.get("opened_at"),
            residual_dropped=residual_dropped,
        )
        direction = 1.0 if pos["side"] == "buy" else -1.0
        pnl = direction * (exit_price - pos["entry_price"]) * qty - fee
        entry_notional = pos["entry_price"] * qty
        pnl_pct = pnl / entry_notional * 100 if entry_notional else 0.0
        self.circuit_breaker.record_trade_result(pnl_pct)
        logger.info(
            "Position closed %s %s at %.2f (entry %.2f, pnl %.2f%%)",
            pos["side"], pos["symbol"], exit_price, pos["entry_price"], pnl_pct,
        )

    @staticmethod
    def _exit_price(pos: dict[str, Any], current_price: float) -> float | None:
        """Return the exit price if ``current_price`` triggers stop or TP, else None."""
        sl = pos.get("stop_loss")
        tp = pos.get("take_profit")
        side = (pos.get("side") or "buy").lower()
        if side == "buy":
            if sl is not None and current_price <= sl:
                return sl
            if tp is not None and current_price >= tp:
                return tp
        else:  # sell / short
            if sl is not None and current_price >= sl:
                return sl
            if tp is not None and current_price <= tp:
                return tp
        return None

    async def _emit_stub_alert(self, symbol: str) -> None:
        """Alert when the strategy fell back to synthetic stub data (no-op without a sink)."""
        if self.alert_store is None and self.alert_bus is None:
            return
        alert = Alert(
            severity="high",
            type="data_fallback",
            message=(
                f"Strategy Agent em modo fallback para {symbol}: decisão baseada em "
                "dados sintéticos (stub). Verifique a conectividade com a exchange."
            ),
            agent_id="strategy_agent",
            pair=symbol,
        )
        if self.alert_store is not None:
            self.alert_store.append(alert)
        if self.alert_bus is not None:
            await self.alert_bus.publish(alert)

    async def _emit_alert(self, symbol: str, issues: Any) -> None:
        """Emit a guardrail alert when risk rejects a signal (no-op without a sink)."""
        if self.alert_store is None and self.alert_bus is None:
            return
        detail = "; ".join(str(i) for i in issues) if issues else "Risk validation failed"
        alert = Alert(
            severity="high",
            type="risk_rejection",
            message=f"Sinal rejeitado pelo Risk Agent ({symbol}): {detail}",
            agent_id="risk_agent",
            pair=symbol,
        )
        if self.alert_store is not None:
            self.alert_store.append(alert)
        if self.alert_bus is not None:
            await self.alert_bus.publish(alert)
