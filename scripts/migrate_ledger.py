"""One-time JSONL→SQLite ledger migration (ADR-003).

Imports an existing append-only ledger (``trades.jsonl``) into the new SQLite
store (``trades.db``), preserving each event's original timestamp. Refuses to run
if the target already has events, so re-running is safe.

    LEDGER_DIR=/app/data/ledger python scripts/migrate_ledger.py

Only needed on hosts that ran an older (JSONL) build and want to keep that
history; a fresh deploy starts straight on SQLite.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))  # allow `import src...` when run as a script

from src.core.db import connection  # noqa: E402
from src.core.ledger import TradingLedger, _ledger_dir  # noqa: E402


def main() -> int:
    jsonl = _ledger_dir() / "trades.jsonl"
    if not jsonl.exists():
        print(f"No legacy ledger at {jsonl}; nothing to migrate.")
        return 0

    led = TradingLedger()  # creates trades.db + schema
    with connection(led.db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM ledger_events").fetchone()[0]
    if existing:
        print(f"{led.db_path} already has {existing} events; refusing to double-import.")
        return 1

    migrated = 0
    with jsonl.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            entry = json.loads(line)
            led.log_decision(
                entry.get("event_type", "unknown"),
                entry.get("data", {}),
                timestamp=entry.get("timestamp"),
            )
            migrated += 1

    print(f"Migrated {migrated} events: {jsonl} -> {led.db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
