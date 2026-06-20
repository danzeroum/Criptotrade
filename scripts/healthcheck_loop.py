#!/usr/bin/env python3
"""Healthcheck for the orchestrator loop (no HTTP endpoint to probe).

Exits 0 when the loop's heartbeat is fresh, 1 otherwise. Used by the
docker-compose `orchestrator` service. Freshness window =
max(180s, 3 x ORCHESTRATOR_INTERVAL_SECONDS) to tolerate a slow cycle.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.orchestration.heartbeat import (  # noqa: E402
    HEARTBEAT_FILENAME,
    is_fresh,
    read_heartbeat,
)


def main() -> int:
    ledger_dir = Path(os.getenv("LEDGER_DIR", ".buildtovalue/ledger"))
    interval = float(os.getenv("ORCHESTRATOR_INTERVAL_SECONDS", "60"))
    max_age = max(180.0, 3 * interval)
    hb = read_heartbeat(ledger_dir / HEARTBEAT_FILENAME)
    if is_fresh(hb, max_age):
        return 0
    print("orchestrator heartbeat stale or missing", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
