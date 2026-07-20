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
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from src.agents.registry import AgentRegistry
from src.core.ledger import TradingLedger
from src.core.pairs import allowed_pairs, operated_pairs, parse_pairs
from src.orchestration.heartbeat import HEARTBEAT_FILENAME, write_heartbeat

logger = logging.getLogger(__name__)

MIN_INTERVAL = 10
MAX_INTERVAL = 3600
DEFAULT_INTERVAL = 60


def _symbols_from_env() -> List[str]:
    """Resolve which symbols the loop trades each cycle.

    ``SYMBOLS`` (comma-separated) is the explicit opt-in for multi-symbol
    trading; entries must be in the ``MARKET_PAIRS`` allowlist so the API/UI can
    validate and view them. Unknown entries are dropped with a warning. When
    ``SYMBOLS`` is unset/empty (or every entry is invalid) the loop trades
    ``BTC/USDT`` only — multi-symbol is opt-in, not automatic, to avoid a
    surprise jump in capital exposure on upgrade.
    """
    # operated_pairs() is the single source of truth (also feeds /v1/pairs); here
    # we additionally warn about entries dropped for not being in the allowlist.
    raw = os.getenv("SYMBOLS", "").strip()
    if raw:
        dropped = [s for s in parse_pairs(raw) if s not in set(allowed_pairs())]
        if dropped:
            logger.warning(
                "Ignoring SYMBOLS not in MARKET_PAIRS allowlist: %s", ", ".join(dropped)
            )
    return operated_pairs()


def _paused_symbols() -> set:
    """N9: the set of currently-paused operated pairs, read fresh each cycle.

    A DB read per cycle (not per pair) — pausing is honoured without a restart,
    unlike adding/removing a pair (which the loop resolves only at boot). Best-effort:
    an absent table / read error yields an empty set (nothing paused), never a crash.
    """
    try:
        from src.core.pairs_store import OperatedPairStore

        return {p["symbol"] for p in OperatedPairStore().list_all() if p["paused"]}
    except Exception:  # pragma: no cover - a paused read must never kill the loop
        logger.warning("Failed to read paused pairs; treating none as paused", exc_info=True)
        return set()


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
        # Heartbeat next to the ledger so a no-HTTP loop is still observable
        # (scripts/healthcheck_loop.py reads it for the container healthcheck).
        self._heartbeat_path = Path(self.ledger.ledger_path).parent / HEARTBEAT_FILENAME

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
        # N6: per-symbol time within the cycle (ms). ADDITIVE — existing consumers
        # read duration_ms/ran/failures unchanged; this is an extra key.
        per_symbol: Dict[str, float] = {}
        # N9: which pairs are paused is read fresh EACH cycle (one query, not a
        # fan-out) so pausing applies without a restart. A paused pair still runs
        # analyze_and_trade — its open positions stay managed; only new orders skip.
        paused_symbols = _paused_symbols()
        try:
            for symbol in self.symbols:
                sym_start = time.monotonic()
                try:
                    result = await self.orchestrator.analyze_and_trade(
                        symbol, paused=symbol in paused_symbols
                    )
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
                finally:
                    per_symbol[symbol] = round((time.monotonic() - sym_start) * 1000, 1)
            for agent_id in ran_agents:
                self.registry.record_cycle(agent_id)
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            self.ledger.log_process_event(
                cycle_id, "agent_cycle_completed", "orchestrator",
                {"duration_ms": duration_ms, "ran": ran_agents,
                 "failures": len(failures), "per_symbol": per_symbol},
            )
            write_heartbeat(self._heartbeat_path, cycle_id)
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
        from src.core.alerts import AlertStore
        from src.core.db import get_db_path
        from src.core.exchange_factory import build_exchange_client
        from src.hitl.config import level_from_env, level_info
        from src.hitl.orders import OrderStore, make_approval_handler
        from src.orchestration.squad_orchestrator import SquadOrchestrator

        # A5: reads the ACTIVE managed connection from the shared SQLite (env
        # fallback when none) and enforces the live-routing gate at startup.
        # Rotating/switching the connection requires an orchestrator restart
        # (declared: no hot-reload).
        exchange = build_exchange_client()  # requires EXCHANGE_DRY_RUN; offline in dry-run
        ledger = TradingLedger()
        db_path = str(get_db_path())
        registry = AgentRegistry(db_path=db_path)  # loop writes cycle_events
        registry.prune_cycle_events()  # bound the cross-process cycle history at startup

        # HITL bridge on the shared db. No guardrails here: the RiskAgent already
        # runs them in the pipeline, so the OrderStore is purely the approval gate.
        order_store = OrderStore(
            ledger,
            threshold_provider=lambda: level_info(level_from_env()).threshold_usdt,
            db_path=db_path,
        )
        handler = approval_handler or make_approval_handler(order_store)

        # Fix #2 bonus — wire the loop's alert sink. Without this the loop ran with
        # alert_store=None, so _emit_stub_alert / _emit_alert / guardrails were no-ops
        # and no data_fallback (or risk) alert ever reached alerts.jsonl for the
        # dispatcher. AlertStore() writes the same LEDGER_DIR/alerts.jsonl the
        # dispatcher tails; the in-process AlertBus is omitted (no SSE subscribers in
        # the loop process — cross-process delivery is via the JSONL file).
        orchestrator = SquadOrchestrator(
            exchange, approval_handler=handler, fill_callback=order_store.mark_filled,
            alert_store=AlertStore(),
        )
        orchestrator.ledger = ledger  # share one ledger between pipeline and loop
        orchestrator.reload_open_positions()  # restore positions + breaker after a restart
        # Explicit symbols win; otherwise resolve from SYMBOLS env (default BTC).
        loop = cls(orchestrator, registry, ledger, symbols=symbols or _symbols_from_env())
        loop.order_store = order_store  # exposed for inspection / future mark_filled
        return loop


__all__ = ["OrchestratorLoop", "AgentExecutionError", "validated_interval"]
