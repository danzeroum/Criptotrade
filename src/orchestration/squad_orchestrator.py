"""Orchestrator for multi-agent trading operations."""
from __future__ import annotations

from typing import Any, Dict
import logging

from src.agents.execution_agent import ExecutionAgent
from src.agents.risk_agent import RiskAgent
from src.agents.strategy_agent import StrategyAgent
from src.core.ledger import TradingLedger

logger = logging.getLogger(__name__)


class SquadOrchestrator:
    """Coordinates strategy, risk, and execution agents."""

    def __init__(self, exchange_client: Any) -> None:
        self.strategy_agent = StrategyAgent()
        self.risk_agent = RiskAgent()
        self.execution_agent = ExecutionAgent(exchange_client)
        self.ledger = TradingLedger()

    async def analyze_and_trade(self, symbol: str, timeframe: str = "1h") -> Dict[str, Any]:
        """Full trading pipeline with agent collaboration."""
        logger.info("Starting analysis", extra={"symbol": symbol, "timeframe": timeframe})

        strategy_result = await self.strategy_agent.execute({
            "symbol": symbol,
            "timeframe": timeframe,
        })

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
            logger.warning("Signal rejected by Risk Agent", extra={"issues": risk_result["validation"]["issues"]})
            return {
                "success": False,
                "reason": "Risk validation failed",
                "issues": risk_result["validation"]["issues"],
            }

        logger.info("⏸️  HITL approval required")
        human_approved = True  # TODO: integrate with real approval flow

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

        return {
            "success": execution_result["success"],
            "order_id": execution_result.get("order_id"),
            "signal": strategy_result["signal"],
            "confidence": strategy_result["confidence"],
        }
