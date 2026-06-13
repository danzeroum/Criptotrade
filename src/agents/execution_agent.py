"""Execution agent for order management."""
from __future__ import annotations

from typing import Any, Dict
from src.agents.base_agent import BaseAgent
from src.core.exchange_client import ExchangeClient
import logging
import uuid

logger = logging.getLogger(__name__)


class ExecutionAgent(BaseAgent):
    """Executes validated trades on exchange."""

    def __init__(self, exchange_client: ExchangeClient) -> None:
        super().__init__("execution")
        self.tools = ["place_order", "cancel_order", "get_order_status"]
        self.exchange = exchange_client
        self.paper_trading = True  # Always true for MVP

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute validated order."""
        if not self.validate_input(task):
            raise ValueError("Invalid execution task")

        signal = task.get("signal", {})
        human_approved = task.get("human_approved", False)
        quantity = task.get("quantity")

        if not human_approved:
            return {
                "success": False,
                "agent": self.agent_type,
                "error": "Human approval required (HITL)",
                "confidence": 0.0
            }

        # ReAct loop for execution
        result = await self._react_execution(signal, quantity)

        decision = {
            "task": task,
            "result": result,
            "confidence": result.get("confidence", 0.0)
        }

        self.log_decision(decision)

        return {
            "success": result["success"],
            "agent": self.agent_type,
            "order_id": result.get("order_id"),
            "executed_price": result.get("executed_price"),
            "fee": result.get("fee", 0.0),
            "confidence": result.get("confidence", 0.0)
        }

    async def _react_execution(
        self, signal: Dict[str, Any], quantity: float | None = None
    ) -> Dict[str, Any]:
        """ReAct pattern for order execution."""
        # Thought
        thought = f"Need to execute {signal['action']} order for {signal.get('symbol')}"
        logger.info(f"[THOUGHT] {thought}")

        # Action
        action = "simulate_order" if self.paper_trading else "place_real_order"
        logger.info(f"[ACTION] {action}")

        # Observation
        if action == "simulate_order":
            observation = await self._simulate_order(signal, quantity)
        else:
            # TODO: Implement real order placement
            observation = {"success": False, "error": "Real trading not implemented"}

        logger.info(f"[OBSERVATION] {observation}")

        # Answer
        confidence = 1.0 if observation["success"] else 0.0
        return {**observation, "confidence": confidence}

    async def _simulate_order(
        self, signal: Dict[str, Any], quantity: float | None
    ) -> Dict[str, Any]:
        """Place a paper order through the exchange so slippage + fee apply.

        Routes through ``ExchangeClient.create_order`` (which always runs
        ``_create_paper_order`` because ``paper_trading`` is True) instead of
        fabricating a fill, so the recorded price/fee are economically real.
        Falls back to a synthetic id when the task carries no sizing, so an
        approved trade is never silently dropped.
        """
        symbol = signal.get("symbol")
        side = str(signal.get("action", "buy")).lower()
        amount = float(quantity) if quantity else 0.0

        if not symbol or amount <= 0:
            logger.warning("No sizing for %s order; recording synthetic paper fill", symbol)
            return {
                "success": True,
                "order_id": "PAPER_" + str(uuid.uuid4())[:8],
                "status": "filled",
                "message": "Paper trade simulated (no sizing)",
            }

        order = await self.exchange.create_order(symbol, "market", side, amount)
        executed_price = order.get("average") or order.get("price")
        fee = (order.get("fee") or {}).get("cost", 0.0)
        status = order.get("status", "filled")
        return {
            "success": status in ("filled", "closed", "open"),
            "order_id": order.get("id"),
            "executed_price": executed_price,
            "fee": fee,
            "status": status,
            "message": "Paper trade executed via exchange",
        }
