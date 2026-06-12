"""Orchestrator for multi-agent trading operations."""
from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Optional

from src.agents.execution_agent import ExecutionAgent
from src.agents.risk_agent import RiskAgent
from src.agents.strategy_agent import StrategyAgent
from src.core.alerts import Alert, AlertBus, AlertStore
from src.core.ledger import TradingLedger

logger = logging.getLogger(__name__)


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

    def __init__(self, ledger: TradingLedger | None = None) -> None:
        self._ledger = ledger
        self._tripped_at: float | None = None
        self._consecutive_losses: int = 0
        self._daily_loss_pct: float = 0.0

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

    def reset_daily(self) -> None:
        """Call once per trading day to reset the daily loss counter."""
        self._daily_loss_pct = 0.0
        if self._tripped_at is not None:
            elapsed = time.time() - self._tripped_at
            if elapsed >= self.COOLDOWN_SECONDS:
                self._reset("daily reset")

    def _trip(self, reason: str) -> None:
        if self._tripped_at is not None:
            return  # already tripped
        self._tripped_at = time.time()
        msg = f"Circuit breaker TRIPPED: {reason}. Cooldown {self.COOLDOWN_SECONDS/3600:.0f}h."
        logger.critical(msg)
        if self._ledger is not None:
            try:
                self._ledger.log_event("circuit_breaker_tripped", {"reason": reason})
            except Exception:
                pass

    def _reset(self, reason: str) -> None:
        self._tripped_at = None
        self._consecutive_losses = 0
        logger.info("Circuit breaker RESET: %s.", reason)
        if self._ledger is not None:
            try:
                self._ledger.log_event("circuit_breaker_reset", {"reason": reason})
            except Exception:
                pass


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
        self.circuit_breaker = CircuitBreaker(ledger=self.ledger)
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

    async def analyze_and_trade(self, symbol: str, timeframe: str = "1h") -> dict[str, Any]:
        """Full trading pipeline with agent collaboration."""
        if self.circuit_breaker.is_open:
            logger.warning("Circuit breaker is OPEN — skipping trade cycle for %s", symbol)
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

        # Check open paper positions against current price on every cycle, even
        # when this cycle generates no new trade (fail-safe: wrap so a close error
        # never blocks the trading pipeline).
        current_price = float(strategy_result["signal"].get("entry_price") or 0.0)
        if current_price > 0:
            try:
                self._check_open_positions(current_price, symbol)
            except Exception:
                logger.warning("Position check failed for %s", symbol, exc_info=True)

        self.ledger.log_signal(agent="strategy", signal=strategy_result["signal"])

        if strategy_result["confidence"] < 0.6:
            logger.info("Signal confidence too low, skipping")
            return {
                "success": False,
                "reason": "Low confidence signal",
                "confidence": strategy_result["confidence"],
            }

        risk_result = await self.risk_agent.execute({
            "signal": strategy_result["signal"],
            "portfolio": {},
        })

        self.ledger.log_validation(agent="risk", validation=risk_result["validation"])

        if not risk_result["approved"]:
            issues = risk_result["validation"]["issues"]
            logger.warning("Signal rejected by Risk Agent", extra={"issues": issues})
            await self._emit_alert(symbol, issues)
            return {
                "success": False,
                "reason": "Risk validation failed",
                "issues": issues,
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
        })

        self.ledger.log_execution(agent="execution", execution=execution_result)

        if execution_result.get("success"):
            self._log_fill(symbol, strategy_result["signal"], execution_result)
            # Complete the manual HITL path: approved -> filled in the OrderStore.
            # No-op for auto-filled orders (mark_filled guards on status='approved').
            if self.fill_callback is not None and self._last_order_ref is not None:
                try:
                    self.fill_callback(self._last_order_ref)
                except Exception:  # pragma: no cover - never break a completed trade
                    logger.warning(
                        "fill_callback failed for %s", self._last_order_ref, exc_info=True
                    )

        # TODO(5b): reset self._last_order_ref = None here so a stale id from this
        # cycle can never leak into the next. Risk is low today (fill_callback only
        # fires on execution success), but resetting is the hygienic close.
        return {
            "success": execution_result["success"],
            "order_id": execution_result.get("order_id"),
            "signal": strategy_result["signal"],
            "confidence": strategy_result["confidence"],
        }

    def _log_fill(self, symbol: str, signal: dict[str, Any], execution: dict[str, Any]) -> None:
        """Record the economic facts of a fill so metrics can value the position.

        Quantity is derived from the signal's ``position_size_pct`` and the
        configured capital. Best-effort: a malformed signal must not break the
        trade that already executed.
        """
        try:
            price = float(signal.get("entry_price") or 0.0)
            size_pct = float(signal.get("position_size_pct") or 0.0)
            if price <= 0 or size_pct <= 0:
                return
            quantity = (self.initial_capital * size_pct / 100.0) / price
            order_id = execution.get("order_id", "UNKNOWN")
            self.ledger.log_fill(
                order_id=order_id,
                symbol=signal.get("symbol", symbol),
                side=signal.get("action", "buy"),
                price=price,
                quantity=quantity,
            )
            # Track in the paper position book so the next cycle can close it
            # at stop-loss or take-profit.
            sl = signal.get("stop_loss")
            tp = signal.get("take_profit")
            self._open_positions[order_id] = {
                "symbol": signal.get("symbol", symbol),
                "side": signal.get("action", "buy").lower(),
                "entry_price": price,
                "quantity": quantity,
                "stop_loss": float(sl) if sl is not None else None,
                "take_profit": float(tp) if tp is not None else None,
                "opened_at": datetime.now(UTC).isoformat(),
            }
        except (TypeError, ValueError):  # pragma: no cover - defensive
            logger.warning("Could not record fill for %s", symbol, exc_info=True)

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
            del self._open_positions[oid]
            self.ledger.log_position_closed(
                order_id=oid,
                symbol=pos["symbol"],
                side=pos["side"],
                entry_price=pos["entry_price"],
                exit_price=exit_price,
                quantity=pos["quantity"],
                opened_at=pos.get("opened_at"),
            )
            direction = 1.0 if pos["side"] == "buy" else -1.0
            pnl = direction * (exit_price - pos["entry_price"]) * pos["quantity"]
            entry_notional = pos["entry_price"] * pos["quantity"]
            pnl_pct = pnl / entry_notional * 100 if entry_notional else 0.0
            self.circuit_breaker.record_trade_result(pnl_pct)
            logger.info(
                "Position closed %s %s at %.2f (entry %.2f, pnl %.2f%%)",
                pos["side"], pos["symbol"], exit_price, pos["entry_price"], pnl_pct,
            )

    @staticmethod
    def _exit_price(pos: dict[str, Any], current_price: float) -> Optional[float]:
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
