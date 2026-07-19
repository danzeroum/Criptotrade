"""/v1/pairs — the dynamic pair source for the console selector (N1).

Thin read-only view over ``src.core.pairs`` (the allowlist / operated set) plus a
per-symbol freshness stamp from the ledger. Supersedes the flat
``/v1/market/pairs``: the selector renders operated (the loop trades these) vs
observable (allowlist, analysable) from here, so changing ``SYMBOLS`` in the env
is reflected without touching the front. Read-only, no secrets — reachable by the
demo principal.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from src.api.deps import get_ledger
from src.api.schemas import APIResponse, OperatedPair, PairsOut
from src.core.db import connection
from src.core.pairs import allowed_pairs, operated_pairs

router = APIRouter(prefix="/pairs", tags=["pairs"])


def _last_cycle_by_symbol(ledger: Any) -> Dict[str, str]:
    """Most recent ``signal_generated`` timestamp per symbol (one indexed query).

    Reads the ledger's ``$.signal.symbol`` JSON path — the same shape
    ``log_signal`` writes — so the selector can show how fresh each pair is.
    Best-effort: a query failure just yields no stamps (status = "aguardando").
    """
    try:
        with connection(ledger.db_path) as conn:
            rows = conn.execute(
                "SELECT json_extract(data,'$.signal.symbol') AS sym,"
                "       MAX(timestamp) AS ts"
                " FROM ledger_events"
                " WHERE event_type='signal_generated'"
                " GROUP BY sym"
            ).fetchall()
        return {r["sym"]: r["ts"] for r in rows if r["sym"]}
    except Exception:  # pragma: no cover - a scrape must never 500 the selector
        return {}


@router.get(
    "",
    response_model=APIResponse[PairsOut],
    summary="Pares operados (SYMBOLS) + observáveis (allowlist) — fonte do seletor",
)
async def get_pairs(ledger: Any = Depends(get_ledger)) -> APIResponse[PairsOut]:
    last_cycle = _last_cycle_by_symbol(ledger)
    operados = [
        OperatedPair(
            symbol=sym,
            last_cycle_at=last_cycle.get(sym),
            status="operando" if last_cycle.get(sym) else "aguardando",
        )
        for sym in operated_pairs()
    ]
    return APIResponse(data=PairsOut(operados=operados, observaveis=allowed_pairs()))
