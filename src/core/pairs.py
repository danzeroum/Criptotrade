"""Single source of truth for the tradeable-pair allowlist (env ``MARKET_PAIRS``).

Shared by the API (pair validation), the trading loop (which symbols to trade)
and the dashboards, so the allowed set never drifts between layers.
"""
from __future__ import annotations

import os
from typing import List

DEFAULT_PAIRS = "BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT"


def parse_pairs(raw: str) -> List[str]:
    """Split a comma-separated pair list into a sorted, upper-cased, de-duped list."""
    return sorted({p.strip().upper() for p in raw.split(",") if p.strip()})


def allowed_pairs() -> List[str]:
    """The configured allowlist from env ``MARKET_PAIRS`` (or the default majors)."""
    return parse_pairs(os.getenv("MARKET_PAIRS", DEFAULT_PAIRS))


def _db_operated_pairs() -> List[str]:
    """Operated pairs from the ``operated_pairs`` table (N8²). ``[]`` if the table
    is absent/empty — best-effort so the loop works before migrations run."""
    try:
        from src.core.pairs_store import OperatedPairStore
        return OperatedPairStore().symbols()
    except Exception:  # pragma: no cover - absent table => env fallback
        return []


def operated_pairs() -> List[str]:
    """Pairs the loop actually trades — **DB > env** (padrão A5, N8²).

    Single source of truth for "operated" — shared by the trading loop
    (which symbols to run) and the ``/v1/pairs`` route (what the selector shows
    as operated), so the two never disagree. Precedence: the ``operated_pairs``
    table wins when non-empty; otherwise the env ``SYMBOLS`` is the fallback
    (retrocompatible). Entries not in the allowlist are dropped; empty/all-invalid
    falls back to ``BTC/USDT`` (multi-symbol is opt-in, never a surprise).
    """
    allowed = set(allowed_pairs())
    db = _db_operated_pairs()
    if db:
        valid = [s for s in db if s in allowed]
        return valid or ["BTC/USDT"]
    raw = os.getenv("SYMBOLS", "").strip()
    if not raw:
        return ["BTC/USDT"]
    valid = [s for s in parse_pairs(raw) if s in allowed]
    return valid or ["BTC/USDT"]


def is_allowed(symbol: str) -> bool:
    """True if ``symbol`` is in the allowlist (case-insensitive)."""
    return symbol.strip().upper() in set(allowed_pairs())
