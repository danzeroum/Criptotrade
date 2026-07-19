"""/v1/pairs — the dynamic pair source for the console selector (N1) + the
DB-managed operated set (N8²).

GET is a thin read-only view over ``src.core.pairs`` (allowlist / operated set)
plus a per-symbol freshness stamp from the ledger — read-only, no secrets,
reachable by the demo principal. The write endpoints (``/operated``) manage the
``operated_pairs`` table (DB > env, padrão A5): adding/removing a pair applies at
the next orchestrator restart (declared), gated behind ``edit_settings`` and
audited as ``config_changed`` scope ``pairs``.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Path

from src.api.authn import Principal, require_perm
from src.api.deps import get_exchange_client, get_ledger
from src.api.schemas import APIResponse, OperatedPair, OperatedPairIn, PairsOut
from src.core.db import connection
from src.core.pairs import allowed_pairs, is_allowed, operated_pairs
from src.core.pairs_store import OperatedPairStore

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
    summary="Pares operados (DB > env) + observáveis (allowlist) — fonte do seletor",
)
async def get_pairs(ledger: Any = Depends(get_ledger)) -> APIResponse[PairsOut]:
    last_cycle = _last_cycle_by_symbol(ledger)
    paused = {p["symbol"]: p["paused"] for p in OperatedPairStore().list_all()}
    operados = [
        OperatedPair(
            symbol=sym,
            last_cycle_at=last_cycle.get(sym),
            status="operando" if last_cycle.get(sym) else "aguardando",
            paused=bool(paused.get(sym, False)),
        )
        for sym in operated_pairs()
    ]
    return APIResponse(data=PairsOut(operados=operados, observaveis=allowed_pairs()))


def _norm(symbol: str) -> str:
    s = symbol.strip().upper()
    return s.replace("-", "/") if "/" not in s else s


async def _validate_addable(symbol: str, client: Any) -> str:
    """Gate an add: quote USDT + allowlist (required) + ccxt existence (best-effort,
    skipped when the client is offline/dry-run — the allowlist is the real gate)."""
    sym = _norm(symbol)
    if not sym.endswith("/USDT"):
        raise HTTPException(status_code=422, detail={
            "error": "invalid_quote", "message": "Só pares cotados em USDT são suportados."})
    if not is_allowed(sym):
        raise HTTPException(status_code=422, detail={
            "error": "not_in_allowlist",
            "message": f"'{sym}' não está na allowlist MARKET_PAIRS.",
            "valid": allowed_pairs()})
    try:
        markets = await client.get_markets()
        if markets and sym not in markets:
            raise HTTPException(status_code=422, detail={
                "error": "unknown_on_exchange", "message": f"'{sym}' não existe na exchange."})
    except HTTPException:
        raise
    except Exception:  # offline / dry-run — allowlist already validated it
        pass
    return sym


@router.post(
    "/operated",
    response_model=APIResponse[PairsOut],
    status_code=201,
    summary="Adiciona um par operado (N8² — aplica no próximo restart do orchestrator)",
)
async def add_operated(
    body: OperatedPairIn = Body(...),
    ledger: Any = Depends(get_ledger),
    client: Any = Depends(get_exchange_client),
    principal: Principal = Depends(require_perm("edit_settings")),
) -> APIResponse[PairsOut]:
    store = OperatedPairStore()
    before = store.symbols()
    sym = await _validate_addable(body.symbol, client)
    store.add(sym)
    after = store.symbols()
    ledger.log_decision("config_changed", {
        "actor": principal.actor, "scope": "pairs",
        "before": {"operated": before}, "after": {"operated": after},
    })
    return await get_pairs(ledger)


@router.delete(
    "/operated/{symbol}",
    response_model=APIResponse[PairsOut],
    summary="Remove um par operado (N8² — aplica no próximo restart do orchestrator)",
)
async def remove_operated(
    symbol: str = Path(...),
    ledger: Any = Depends(get_ledger),
    principal: Principal = Depends(require_perm("edit_settings")),
) -> APIResponse[PairsOut]:
    store = OperatedPairStore()
    before = store.symbols()
    if not store.remove(_norm(symbol)):
        raise HTTPException(status_code=404, detail={
            "error": "not_operated", "message": f"'{_norm(symbol)}' não está no conjunto operado."})
    after = store.symbols()
    ledger.log_decision("config_changed", {
        "actor": principal.actor, "scope": "pairs",
        "before": {"operated": before}, "after": {"operated": after},
    })
    return await get_pairs(ledger)
