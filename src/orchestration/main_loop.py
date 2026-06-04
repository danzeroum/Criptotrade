"""Dedicated entrypoint for the continuous orchestrator loop (Option A).

Runs **outside** the API process — see the ``orchestrator`` service in
``docker-compose.yml``. A trading loop must not share a lifecycle with uvicorn:
otherwise an API restart would stop trading and vice-versa.

Run:
    python -m src.orchestration.main_loop

Requires ``EXCHANGE_DRY_RUN`` (the ExchangeClient refuses to start otherwise).

HITL: the loop wires the live cross-process bridge (``make_approval_handler`` over
an ``OrderStore`` on the shared SQLite db). Orders within the env autonomy
threshold auto-approve and fill; larger ones wait (pending) for a human to approve
via the API on the same db. Full observability (XES events, cycle counters) is
emitted either way.
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
    # Live HITL bridge: orders within the autonomy threshold auto-approve; larger
    # ones wait (pending) for a human to approve via the API on the shared db.
    loop = OrchestratorLoop.from_env()

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
