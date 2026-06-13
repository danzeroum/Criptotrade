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


def is_allowed(symbol: str) -> bool:
    """True if ``symbol`` is in the allowlist (case-insensitive)."""
    return symbol.strip().upper() in set(allowed_pairs())
