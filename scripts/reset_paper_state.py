"""Reset the paper-trading operational state (clean baseline) — TWO surfaces.

The reset clears live operational state across the two databases:

  * ``LEDGER_DIR/trades.db`` (the file ``TradingLedger`` owns): the
    circuit-breaker state + the open-position book.
  * ``criptotrade.db`` (the app db): the ``orders`` table (the HITL/Orders
    view — every pending/approved/filled order the operator sees).

so the orchestrator boots with a CLOSED breaker, an EMPTY book, and no stale
orders. Hand-clearing means writing SQL against the *right* database — easy to
aim at the wrong file by mistake. This does it for you.

Why it exists: switching the price source (e.g. synthetic -> real) can leave
legacy paper positions whose stops sit far from the new market. They all stop
out at once on the first real cycle and trip the daily-loss breaker, which then
blocks every subsequent cycle. A silent stub-data run can also leave stub orders.

Realised-P&L / audit history in ``ledger_events`` (in ``trades.db``) is NOT
touched — that is the audit trail. Only the live breaker / position / order
state is cleared; the ``orders`` table is operational, not the trail.

Usage (SEMPRE como módulo, a partir da raiz do repo — `python scripts/reset_paper_state.py`
daria ``ModuleNotFoundError: src``, pois a raiz não estaria no ``sys.path``):
    python -m scripts.reset_paper_state              # prompts for confirmation
    python -m scripts.reset_paper_state --yes        # skip the prompt (non-interactive)
    python -m scripts.reset_paper_state --dry-run    # report only, change nothing

Na VPS (dockerizado): pare o orchestrator para ele recarregar o estado limpo em vez
de re-persistir o breaker em memória; rode o reset DENTRO do container ``app`` (que
segue DE PÉ e compartilha o mesmo volume ``./data`` — ``exec`` exige um container
rodando, por isso mira ``app``, não o ``orchestrator`` parado). ``--yes`` é obrigatório
porque ``docker compose exec`` não tem TTY para o prompt (sem ele → EOFError):
    docker compose -f docker-compose.vps.yml stop orchestrator
    docker compose -f docker-compose.vps.yml exec app python -m scripts.reset_paper_state --yes
    docker compose -f docker-compose.vps.yml start orchestrator
"""
from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from typing import Any

from src.core.db import get_db_path
from src.core.ledger import TradingLedger
from src.hitl.orders import OrderStore
from src.orchestration.position_store import (
    PositionStore,
    clear_circuit_state,
    load_circuit_state,
)

DbPathProvider = Callable[[], Any]


def _describe(db_provider: DbPathProvider) -> tuple[int, dict[str, Any] | None]:
    return PositionStore(db_provider).count(), load_circuit_state(db_provider)


def reset_paper_state(
    db_provider: DbPathProvider,
    *,
    order_store: OrderStore | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Clear the breaker + open-position book (+ operational orders). Summary dict.

    ``order_store`` (the app-db ``orders`` table) is cleared alongside the ledger-db
    breaker/book when provided; omit it to reset only the ledger-db surfaces.
    With ``dry_run=True`` nothing is written; the ``*_cleared`` fields report what
    *would* be removed.
    """
    positions_before, breaker_before = _describe(db_provider)
    orders_before = order_store.count() if order_store is not None else 0
    if dry_run:
        positions_cleared = positions_before
        breaker_cleared = breaker_before is not None
        orders_cleared = orders_before
    else:
        positions_cleared = PositionStore(db_provider).clear()
        breaker_cleared = clear_circuit_state(db_provider)
        orders_cleared = order_store.clear() if order_store is not None else 0
    return {
        "positions_before": positions_before,
        "breaker_before": breaker_before,
        "positions_cleared": positions_cleared,
        "breaker_cleared": breaker_cleared,
        "orders_before": orders_before,
        "orders_cleared": orders_cleared,
        "dry_run": dry_run,
    }


def _print_state(
    ledger_db_path: Any,
    app_db_path: Any,
    positions: int,
    breaker: dict[str, Any] | None,
    orders: int,
) -> None:
    print(f"Ledger db (trades.db):  {ledger_db_path}")
    print(f"App db (criptotrade.db): {app_db_path}")
    print(f"Open positions: {positions}")
    print(f"Orders (operational):    {orders}")
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
    app_db_path = get_db_path()
    order_store = OrderStore(
        ledger,
        threshold_provider=lambda: 0.0,  # read/clear only; no order ever submitted here
        db_path=str(app_db_path),
    )

    def db_provider() -> Any:
        return ledger.db_path

    positions, breaker = _describe(db_provider)
    orders = order_store.count()
    _print_state(ledger.db_path, app_db_path, positions, breaker, orders)

    if args.dry_run:
        print("\n--dry-run: no changes made.")
        return 0

    if positions == 0 and breaker is None and orders == 0:
        print("\nNothing to reset — breaker closed, book empty, no orders.")
        return 0

    if not args.yes:
        try:
            reply = input(
                "\nClear breaker + open-position book + orders? [y/N] "
            ).strip().lower()
        except EOFError:
            # Sem TTY (ex.: `docker compose exec` sem -it) o prompt não pode ser
            # respondido — aborta limpo apontando --yes, em vez de estourar um
            # traceback de EOFError.
            print("\nSem TTY para confirmar. Rode de novo com --yes para pular o prompt.")
            return 1
        if reply not in ("y", "yes"):
            print("Aborted.")
            return 1

    result = reset_paper_state(db_provider, order_store=order_store)
    print(
        f"\nCleared {result['positions_cleared']} open position(s) and "
        f"{result['orders_cleared']} order(s); "
        f"breaker {'cleared' if result['breaker_cleared'] else 'was already closed'}."
    )
    print("The audit trail (ledger_events) was left intact.")
    print("Restart the orchestrator so it reloads the cleared state:")
    print("  docker compose -f docker-compose.vps.yml restart orchestrator")
    return 0


if __name__ == "__main__":
    sys.exit(main())
