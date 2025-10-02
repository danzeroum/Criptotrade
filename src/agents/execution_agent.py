"""Execution agent for order management."""
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

        if not human_approved:
            return {
                "success": False,
                "agent": self.agent_type,
                "error": "Human approval required (HITL)",
                "confidence": 0.0
            }

        # ReAct loop for execution
        result = await self._react_execution(signal)

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
            "confidence": result.get("confidence", 0.0)
        }

    async def _react_execution(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """ReAct pattern for order execution."""
        # Thought
        thought = f"Need to execute {signal['action']} order for {signal.get('symbol')}"
        logger.info(f"[THOUGHT] {thought}")

        # Action
        if self.paper_trading:
            action = "simulate_order"
        else:
            action = "place_real_order"

        logger.info(f"[ACTION] {action}")

        # Observation
        if action == "simulate_order":
            observation = {
                "success": True,
                "order_id": "PAPER_" + str(uuid.uuid4())[:8],
                "status": "filled",
                "message": "Paper trade simulated successfully"
            }
        else:
            # TODO: Implement real order placement
            observation = {"success": False, "error": "Real trading not implemented"}

        logger.info(f"[OBSERVATION] {observation}")

        # Answer
        confidence = 1.0 if observation["success"] else 0.0
        return {**observation, "confidence": confidence}
