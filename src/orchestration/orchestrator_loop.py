"""Continuous orchestrator loop (Phase 4b-iii).

Drives the trading pipeline on a fixed interval and feeds the observability layer:
every cycle writes XES process events (`agent_cycle_started` / `_completed`, and
`_failed` on error) and bumps the in-memory cycle counters that `/v1/agents`
serves.

Contracts:
* ``ORCHESTRATOR_INTERVAL_SECONDS`` — env, validated ``10 <= n <= 3600`` (default
  60). Out of range → ``ValueError`` at construction (same fail-loud pattern as
  ``EXCHANGE_DRY_RUN``).
* A failing agent never tears the loop down: the exception is caught, an
  ``agent_cycle_failed`` event is emitted, and the loop proceeds to the next
  interval.
* The ``ExchangeClient`` is instantiated inside :meth:`from_env` — the first real
  wiring of the client — with ``EXCHANGE_DRY_RUN`` already governing its mode.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence

from src.agents.registry import AgentRegistry
from src.core.ledger import TradingLedger

logger = logging.getLogger(__name__)

MIN_INTERVAL = 10
MAX_INTERVAL = 3600
DEFAULT_INTERVAL = 60


class AgentExecutionError(Exception):
    """Raised by an agent step so the loop can attribute the failure to it."""

    def __init__(self, agent_id: str, message: str) -> None:
        self.agent_id = agent_id
        super().__init__(f"{agent_id}: {message}")


def validated_interval(value: Optional[int] = None) -> int:
    """Resolve + validate the loop interval (env when ``value`` is None)."""
    raw = value if value is not None else os.getenv("ORCHESTRATOR_INTERVAL_SECONDS", str(DEFAULT_INTERVAL))
    try:
        interval = int(raw)
    except (TypeError, ValueError):
        raise ValueError(
            f"ORCHESTRATOR_INTERVAL_SECONDS inválido: {raw!r}. "
            f"Use um inteiro entre {MIN_INTERVAL} e {MAX_INTERVAL} segundos."
        )
    if not (MIN_INTERVAL <= interval <= MAX_INTERVAL):
        raise ValueError(
            f"ORCHESTRATOR_INTERVAL_SECONDS={interval} fora do range "
            f"[{MIN_INTERVAL}, {MAX_INTERVAL}]. Ajuste para um valor seguro."
        )
    return interval


class OrchestratorLoop:
    """Periodically runs the trading pipeline and records observability events."""

    def __init__(
        self,
        orchestrator: Any,
        registry: AgentRegistry,
        ledger: TradingLedger,
        symbols: Optional[Sequence[str]] = None,
        interval_seconds: Optional[int] = None,
    ) -> None:
        self.interval = validated_interval(interval_seconds)
        self.orchestrator = orchestrator
        self.registry = registry
        self.ledger = ledger
        self.symbols: List[str] = list(symbols) if symbols else ["BTC/USDT"]
        # asyncio.Event gives a clean, race-free shutdown: stop() wakes the
        # interval wait immediately instead of waiting out the full sleep.
        self._stop_event = asyncio.Event()

    # ------------------------------------------------------------------- cycle
    async def run_cycle(self) -> Dict[str, Any]:
        """Run exactly one cycle. Never raises on agent failure (fail-soft)."""
        cycle_id = "cycle_" + uuid.uuid4().hex[:8]
        self.ledger.log_process_event(
            cycle_id, "agent_cycle_started", "orchestrator",
            {"interval_seconds": self.interval, "symbols": self.symbols},
        )
        start = time.monotonic()
        ran_agents: List[str] = []
        failures: List[Dict[str, str]] = []
        try:
            for symbol in self.symbols:
                try:
                    result = await self.orchestrator.analyze_and_trade(symbol)
                    agents = ["strategy", "risk"]
                    if isinstance(result, dict) and result.get("order_id"):
                        agents.append("execution")
                    ran_agents.extend(agents)
                except Exception as exc:  # fail-soft: one symbol/agent never kills the loop
                    agent_id = getattr(exc, "agent_id", "pipeline")
                    failures.append({"agent_id": agent_id, "error": str(exc)})
                    self.ledger.log_process_event(
                        cycle_id, "agent_cycle_failed", agent_id,
                        {"error": str(exc), "symbol": symbol},
                    )
                    logger.warning("Agent cycle failure on %s: %s", symbol, exc)
            for agent_id in ran_agents:
                self.registry.record_cycle(agent_id)
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            self.ledger.log_process_event(
                cycle_id, "agent_cycle_completed", "orchestrator",
                {"duration_ms": duration_ms, "ran": ran_agents, "failures": len(failures)},
            )
        return {"cycle_id": cycle_id, "ran": ran_agents, "failures": failures}

    # -------------------------------------------------------------------- loop
    async def run_forever(self) -> None:
        """Run cycles until :meth:`stop` is called, sleeping ``interval`` between.

        The interval wait is interruptible: ``stop()`` returns immediately rather
        than blocking for the remainder of the current sleep.
        """
        self._stop_event.clear()
        logger.info("Orchestrator loop starting (interval=%ss)", self.interval)
        while not self._stop_event.is_set():
            await self.run_cycle()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                pass  # interval elapsed → run the next cycle
        logger.info("Orchestrator loop stopped")

    def stop(self) -> None:
        self._stop_event.set()

    # ------------------------------------------------------------------ wiring
    @classmethod
    def from_env(
        cls,
        symbols: Optional[Sequence[str]] = None,
        approval_handler: Any = None,
    ) -> "OrchestratorLoop":
        """Real wiring: ExchangeClient (mode = EXCHANGE_DRY_RUN) + the live HITL
        bridge.

        The default ``approval_handler`` is now :func:`make_approval_handler` over
        an ``OrderStore`` on the **shared** SQLite db (the same file the API
        reads/writes), so the HITL cycle runs cross-process: the loop submits a
        pending order, the API approves it, the loop polls and proceeds. Orders
        within the env autonomy threshold auto-approve (Model B → filled).

        NOTE (follow-up): for the *manual* path, the order reaches ``approved`` and
        the loop executes, but the OrderStore order is not yet transitioned to
        ``filled`` post-execution — the handler returns a bool, so the orchestrator
        lacks the order id to call ``mark_filled``. Linking them is the next step.
        """
        from src.core.db import get_db_path
        from src.core.exchange_client import ExchangeClient
        from src.hitl.config import level_from_env, level_info
        from src.hitl.orders import OrderStore, make_approval_handler
        from src.orchestration.squad_orchestrator import SquadOrchestrator

        exchange = ExchangeClient()  # requires EXCHANGE_DRY_RUN; offline in dry-run
        ledger = TradingLedger()
        db_path = str(get_db_path())
        registry = AgentRegistry(db_path=db_path)  # loop writes cycle_events

        # HITL bridge on the shared db. No guardrails here: the RiskAgent already
        # runs them in the pipeline, so the OrderStore is purely the approval gate.
        order_store = OrderStore(
            ledger,
            threshold_provider=lambda: level_info(level_from_env()).threshold_usdt,
            db_path=db_path,
        )
        handler = approval_handler or make_approval_handler(order_store)

        orchestrator = SquadOrchestrator(
            exchange, approval_handler=handler, fill_callback=order_store.mark_filled,
        )
        orchestrator.ledger = ledger  # share one ledger between pipeline and loop
        loop = cls(orchestrator, registry, ledger, symbols=symbols)
        loop.order_store = order_store  # exposed for inspection / future mark_filled
        return loop


__all__ = ["OrchestratorLoop", "AgentExecutionError", "validated_interval"]
