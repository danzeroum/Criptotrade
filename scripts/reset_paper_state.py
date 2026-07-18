"""Reset the paper-trading circuit breaker + open-position book (clean baseline).

The breaker state and the open-position book persist in the LEDGER database
(``LEDGER_DIR/trades.db`` — the file ``TradingLedger`` owns, NOT the app db
``criptotrade.db``, which holds auth/connections). This wipes both so the
orchestrator boots with a CLOSED breaker and an EMPTY book.

Why it exists: switching the price source (e.g. synthetic -> real) can leave
legacy paper positions whose stops sit far from the new market. They all stop
out at once on the first real cycle and trip the daily-loss breaker, which then
blocks every subsequent cycle. Hand-clearing the state means writing SQL against
the *right* database — easy to aim at ``criptotrade.db`` by mistake. This does it
for you.

Realised-P&L history in ``ledger_events`` is NOT touched (that is the audit
trail); only the live breaker/position state is cleared.

Usage:
    python -m scripts.reset_paper_state              # prompts for confirmation
    python -m scripts.reset_paper_state --yes        # skip the prompt
    python -m scripts.reset_paper_state --dry-run    # report only, change nothing

Stop the orchestrator first (or restart it after) so it reloads the cleared
state instead of re-persisting the in-memory breaker:
    docker compose -f docker-compose.vps.yml stop orchestrator
    python -m scripts.reset_paper_state --yes
    docker compose -f docker-compose.vps.yml start orchestrator
"""
from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from typing import Any

from src.core.ledger import TradingLedger
from src.orchestration.position_store import (
    PositionStore,
    clear_circuit_state,
    load_circuit_state,
)

DbPathProvider = Callable[[], Any]


def _describe(db_provider: DbPathProvider) -> tuple[int, dict[str, Any] | None]:
    return PositionStore(db_provider).count(), load_circuit_state(db_provider)


def reset_paper_state(db_provider: DbPathProvider, *, dry_run: bool = False) -> dict[str, Any]:
    """Clear the breaker + open-position book. Returns a summary dict.

    With ``dry_run=True`` nothing is written; the ``*_cleared`` fields report what
    *would* be removed.
    """
    positions_before, breaker_before = _describe(db_provider)
    if dry_run:
        positions_cleared = positions_before
        breaker_cleared = breaker_before is not None
    else:
        positions_cleared = PositionStore(db_provider).clear()
        breaker_cleared = clear_circuit_state(db_provider)
    return {
        "positions_before": positions_before,
        "breaker_before": breaker_before,
        "positions_cleared": positions_cleared,
        "breaker_cleared": breaker_cleared,
        "dry_run": dry_run,
    }


def _print_state(db_path: Any, positions: int, breaker: dict[str, Any] | None) -> None:
    print(f"Ledger db: {db_path}")
    print(f"Open positions: {positions}")
    if breaker is None:
        print("Circuit breaker: closed (no persisted state)")
    else:
        print(
            "Circuit breaker: TRIPPED"
            f" (tripped_at={breaker['tripped_at']}"
            f" consecutive_losses={breaker['consecutive_losses']}"
            f" daily_loss_pct={breaker['daily_loss_pct']:.2f})"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reset the paper breaker + open-position book (in the ledger db)."
    )
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report current state without changing anything.",
    )
    args = parser.parse_args(argv)

    ledger = TradingLedger()

    def db_provider() -> Any:
        return ledger.db_path

    positions, breaker = _describe(db_provider)
    _print_state(ledger.db_path, positions, breaker)

    if args.dry_run:
        print("\n--dry-run: no changes made.")
        return 0

    if positions == 0 and breaker is None:
        print("\nNothing to reset — breaker closed and book already empty.")
        return 0

    if not args.yes:
        reply = input("\nClear breaker + open-position book? [y/N] ").strip().lower()
        if reply not in ("y", "yes"):
            print("Aborted.")
            return 1

    result = reset_paper_state(db_provider)
    print(
        f"\nCleared {result['positions_cleared']} open position(s); "
        f"breaker {'cleared' if result['breaker_cleared'] else 'was already closed'}."
    )
    print("Restart the orchestrator so it reloads the cleared state:")
    print("  docker compose -f docker-compose.vps.yml restart orchestrator")
    return 0


if __name__ == "__main__":
    sys.exit(main())
