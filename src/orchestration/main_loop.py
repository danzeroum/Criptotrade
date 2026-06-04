"""Dedicated entrypoint for the continuous orchestrator loop (Option A).

Runs **outside** the API process — see the ``orchestrator`` service in
``docker-compose.yml``. A trading loop must not share a lifecycle with uvicorn:
otherwise an API restart would stop trading and vice-versa.

Run:
    python -m src.orchestration.main_loop

Requires ``EXCHANGE_DRY_RUN`` (the ExchangeClient refuses to start otherwise).

HITL note: with no cross-process approval bridge wired yet, the loop runs
**fail-closed** — no ``approval_handler`` means no order is executed. The loop
still drives strategy + risk and emits the full observability trail (XES events,
cycle counters). Wiring the approval bridge (Redis or HTTP) is the next decision.
"""
from __future__ import annotations

import asyncio
import logging
import signal

from src.core.db import init_db
from src.orchestration.orchestrator_loop import OrchestratorLoop

logger = logging.getLogger(__name__)


async def _amain() -> None:
    init_db()  # ensure the shared SQLite schema exists before the loop runs
    loop = OrchestratorLoop.from_env()  # fail-closed HITL until the bridge is wired

    running_loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            running_loop.add_signal_handler(sig, loop.stop)
        except NotImplementedError:  # pragma: no cover - e.g. non-Unix
            pass

    logger.info("Orchestrator entrypoint starting (interval=%ss)", loop.interval)
    await loop.run_forever()
    logger.info("Orchestrator entrypoint exited cleanly")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
