"""/v1/desk/summary — the Mesa Multi-Ativo batch snapshot (N2).

ONE request returns every operated pair's live state: price + 24h change, regime,
latest signal (action + confidence), open position (side + unrealized P&L) and
freshness. The console never fans out per pair — the fan-out over OHLCV happens
here, concurrently (``asyncio.gather``), behind a short shared TTL cache so
polling the Mesa doesn't hammer the exchange as pairs grow. ``as_of`` is always
the real candle age (even on a cache hit), never the cache time. Read-only, no
secrets — reachable by the demo principal.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends

from src.api.deps import get_exchange_client, get_ledger
from src.api.routes.market import _REGIME_LABELS, _as_of
from src.api.schemas import APIResponse, DeskRow, DeskSummaryOut
from src.core.config import settings
from src.core.db import connection
from src.core.pairs import operated_pairs
from src.core.pairs_store import OperatedPairStore

router = APIRouter(prefix="/desk", tags=["desk"])

# Shared cache window (5–10s per plan): bounds staleness AND the exchange
# rate-limit as the operated set grows. as_of is derived from the candle itself,
# so a cache hit still reports the honest market-data age.
_OHLCV_TTL_S = 8.0
_OHLCV_CACHE: Dict[Tuple[str, str], Tuple[list, float]] = {}


async def _ohlcv(symbol: str, client: Any, tf: str = "1h", limit: int = 150) -> Optional[list]:
    """TTL-cached OHLCV for a pair. Serves stale on a transient failure, else None
    (the pair degrades gracefully instead of failing the whole batch)."""
    key = (symbol, tf)
    hit = _OHLCV_CACHE.get(key)
    if hit and (time.monotonic() - hit[1]) < _OHLCV_TTL_S:
        return hit[0]
    try:
        data = await client.fetch_ohlcv(symbol, timeframe=tf, limit=limit)
    except Exception:
        return hit[0] if hit else None
    _OHLCV_CACHE[key] = (data, time.monotonic())
    return data


def _regime_of(ohlcv: list) -> str:
    """Best-effort regime from OHLCV; 'unknown' if TA/numpy is unavailable."""
    try:
        from src.analysis.indicators import TechnicalAnalyzer
        from src.analysis.regime_detector import detect_regime
        ind = TechnicalAnalyzer(ohlcv).get_latest()
        return detect_regime(
            ema_fast=ind.ema_fast, ema_slow=ind.ema_slow,
            atr=ind.atr, current_price=ind.current_price,
        )
    except Exception:
        return "unknown"


def _latest_signals(ledger: Any) -> Dict[str, dict]:
    """Latest signal per symbol (action + confidence). SQLite returns the bare
    columns from the MAX(timestamp) row of each group."""
    try:
        with connection(ledger.db_path) as conn:
            rows = conn.execute(
                "SELECT json_extract(data,'$.signal.symbol') AS sym,"
                "       json_extract(data,'$.signal.action') AS action,"
                "       json_extract(data,'$.confidence') AS confidence,"
                "       MAX(timestamp) AS ts"
                " FROM ledger_events WHERE event_type='signal_generated' GROUP BY sym"
            ).fetchall()
        return {
            r["sym"]: {"action": r["action"], "confidence": r["confidence"], "ts": r["ts"]}
            for r in rows if r["sym"]
        }
    except Exception:  # pragma: no cover - a scrape must never 500 the Mesa
        return {}


def _parse_dt(ts: Any) -> Optional[datetime]:
    """Parse an ISO ledger timestamp to datetime (None on empty/invalid)."""
    try:
        return datetime.fromisoformat(ts) if ts else None
    except (ValueError, TypeError):
        return None


def _open_positions(ledger: Any) -> List[dict]:
    """Open paper positions (one row per lot). Empty if the table doesn't exist yet."""
    try:
        with connection(ledger.db_path) as conn:
            rows = conn.execute(
                "SELECT symbol, side, entry_price, quantity FROM open_positions"
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


@router.get(
    "/summary",
    response_model=APIResponse[DeskSummaryOut],
    summary="Snapshot de todos os pares operados em 1 request (Mesa Multi-Ativo)",
)
async def desk_summary(
    client: Any = Depends(get_exchange_client),
    ledger: Any = Depends(get_ledger),
) -> APIResponse[DeskSummaryOut]:
    symbols = operated_pairs()
    signals = _latest_signals(ledger)
    lots = _open_positions(ledger)
    # N9: which pairs are paused — one query, surfaced per row for the Mesa badge.
    paused_map = {p["symbol"]: p["paused"] for p in OperatedPairStore().list_all()}

    # Aggregate open lots per symbol (side, qty, notional-weighted entry).
    by_symbol: Dict[str, dict] = {}
    for lot in lots:
        agg = by_symbol.setdefault(lot["symbol"], {"side": lot["side"], "qty": 0.0, "notional": 0.0})
        agg["qty"] += lot["quantity"] or 0.0
        agg["notional"] += (lot["entry_price"] or 0.0) * (lot["quantity"] or 0.0)

    # Backend fan-out over OHLCV — concurrent, behind the TTL cache.
    ohlcvs = await asyncio.gather(*[_ohlcv(sym, client) for sym in symbols])

    rows: List[DeskRow] = []
    signals_active = 0
    allocated = 0.0
    for sym, ohlcv in zip(symbols, ohlcvs):
        row = DeskRow(symbol=sym, paused=bool(paused_map.get(sym, False)))
        if ohlcv:
            last = float(ohlcv[-1][4])
            ref = float(ohlcv[-25][4]) if len(ohlcv) >= 25 else float(ohlcv[0][4])
            row.last = round(last, 8)
            row.change_24h_pct = round((last - ref) / ref * 100, 4) if ref else 0.0
            regime = _regime_of(ohlcv)
            row.regime = regime
            row.regime_label = _REGIME_LABELS.get(regime, regime)
            row.as_of = _as_of(ohlcv)

        sig = signals.get(sym)
        if sig:
            row.signal_action = sig["action"]
            row.signal_confidence = sig["confidence"]
            row.last_cycle_at = _parse_dt(sig["ts"])
            if (sig["confidence"] or 0) >= 0.6:
                signals_active += 1

        pos = by_symbol.get(sym)
        if pos and pos["qty"]:
            entry = pos["notional"] / pos["qty"]
            row.position_side = pos["side"]
            row.position_qty = round(pos["qty"], 8)
            row.position_entry = round(entry, 8)
            allocated += pos["notional"]
            if row.last is not None:
                sign = 1.0 if str(pos["side"]).lower() == "buy" else -1.0
                row.unrealized_pnl = round((row.last - entry) * pos["qty"] * sign, 2)

        rows.append(row)

    # Actionable rises: active signal → open position → confidence desc → alpha.
    rows.sort(key=lambda r: (
        0 if (r.signal_confidence or 0) >= 0.6 else 1,
        0 if r.position_side else 1,
        -(r.signal_confidence or 0.0),
        r.symbol,
    ))

    capital = float(settings.initial_capital)
    return APIResponse(data=DeskSummaryOut(
        rows=rows,
        slots_used=len(lots),
        slots_max=int(settings.max_concurrent_positions),
        capital_allocated=round(allocated, 2),
        capital_free=round(max(0.0, capital - allocated), 2),
        signals_active=signals_active,
    ))
