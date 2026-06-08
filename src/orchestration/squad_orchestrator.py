"""Orchestrator for multi-agent trading operations."""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional
import logging

from src.agents.execution_agent import ExecutionAgent
from src.agents.risk_agent import RiskAgent
from src.agents.strategy_agent import StrategyAgent
from src.core.alerts import Alert, AlertBus, AlertStore
from src.core.ledger import TradingLedger

logger = logging.getLogger(__name__)


class SquadOrchestrator:
    """Coordinates strategy, risk, and execution agents."""

    def __init__(
        self,
        exchange_client: Any,
        approval_handler: Optional[Callable[[Dict[str, Any]], Awaitable[bool]]] = None,
        initial_capital: float = 10_000.0,
        alert_store: Optional[AlertStore] = None,
        alert_bus: Optional[AlertBus] = None,
        fill_callback: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self.strategy_agent = StrategyAgent(exchange_client=exchange_client)
        self.risk_agent = RiskAgent()
        self.execution_agent = ExecutionAgent(exchange_client)
        self.ledger = TradingLedger()
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
        self._last_order_ref: Optional[str] = None
        # Wire the RiskAgent's guardrails to publish each violation as an alert.
        if alert_store is not None:
            from src.core.alerts import make_guardrail_sink

            self.risk_agent.guardrails.alert_sink = make_guardrail_sink(alert_store)

    async def _request_human_approval(self, order: Dict[str, Any]) -> bool:
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

    async def analyze_and_trade(self, symbol: str, timeframe: str = "1h") -> Dict[str, Any]:
        """Full trading pipeline with agent collaboration."""
        logger.info("Starting analysis", extra={"symbol": symbol, "timeframe": timeframe})

        strategy_result = await self.strategy_agent.execute({
            "symbol": symbol,
            "timeframe": timeframe,
        })

        # Ensure the signal carries the symbol so the order records the real pair
        # (the demo strategy stub omits it) — fixes orders showing pair="UNKNOWN".
        strategy_result["signal"].setdefault("symbol", symbol)

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
                    logger.warning("fill_callback failed for %s", self._last_order_ref, exc_info=True)

        # TODO(5b): reset self._last_order_ref = None here so a stale id from this
        # cycle can never leak into the next. Risk is low today (fill_callback only
        # fires on execution success), but resetting is the hygienic close.
        return {
            "success": execution_result["success"],
            "order_id": execution_result.get("order_id"),
            "signal": strategy_result["signal"],
            "confidence": strategy_result["confidence"],
        }

    def _log_fill(self, symbol: str, signal: Dict[str, Any], execution: Dict[str, Any]) -> None:
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
            self.ledger.log_fill(
                order_id=execution.get("order_id", "UNKNOWN"),
                symbol=signal.get("symbol", symbol),
                side=signal.get("action", "buy"),
                price=price,
                quantity=quantity,
            )
        except (TypeError, ValueError):  # pragma: no cover - defensive
            logger.warning("Could not record fill for %s", symbol, exc_info=True)

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
