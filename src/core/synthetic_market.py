"""Deterministic synthetic market data for ``EXCHANGE_DRY_RUN``.

Every value is a **pure function of ``(base_price, timestamp)``** — same input,
same output, always. No randomness, so dry-run sessions and tests are fully
reproducible (mock ``time.time()`` to pin the timestamp).
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Dict, List, Optional

# Timeframe string -> seconds. Defaults to 1h for anything unmapped.
_TF_SECONDS: Dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


def timeframe_seconds(timeframe: str) -> int:
    return _TF_SECONDS.get(timeframe, 3600)


# Per-symbol synthetic anchors (USDT). ``BTC/USDT`` is intentionally absent: it
# stays anchored to ``DRY_RUN_BASE_PRICE`` (the legacy single knob) so existing
# behaviour is preserved. Anything not listed here gets a deterministic
# hash-derived price so two unmapped pairs never collapse onto the same value.
_DEFAULT_BASES: Dict[str, float] = {
    "ETH/USDT": 3000.0,
    "SOL/USDT": 150.0,
    "BNB/USDT": 600.0,
    "XRP/USDT": 0.5,
}


def parse_base_prices(raw: str) -> Dict[str, float]:
    """Parse ``DRY_RUN_BASE_PRICES`` (``BTC/USDT=50000,ETH/USDT=3000``) into a map.

    Malformed entries are skipped — a bad override must never crash startup.
    """
    out: Dict[str, float] = {}
    for item in raw.split(","):
        item = item.strip()
        if not item or "=" not in item:
            continue
        sym, _, val = item.partition("=")
        try:
            out[sym.strip().upper()] = float(val.strip())
        except ValueError:
            continue
    return out


def _hash_base(symbol: str) -> float:
    """Deterministic pseudo-price for an unmapped symbol, in a sane band.

    Uses ``hashlib`` (not the salted built-in ``hash()``) so the value is stable
    across processes and test runs. Range ~[10, 10_010).
    """
    digest = int(hashlib.sha256(symbol.upper().encode()).hexdigest(), 16)
    return round(10.0 + (digest % 1_000_000) / 100.0, 2)


def base_price_for(
    symbol: str,
    default_base: float,
    overrides: Optional[Dict[str, float]] = None,
) -> float:
    """Resolve a deterministic per-symbol base price for synthetic market data.

    Precedence: ``overrides`` (from env ``DRY_RUN_BASE_PRICES``) → built-in
    ``_DEFAULT_BASES`` → ``default_base`` for ``BTC/USDT`` (the legacy
    ``DRY_RUN_BASE_PRICE`` knob) → a hash-derived band for any other symbol.
    """
    sym = symbol.upper()
    if overrides and sym in overrides:
        return overrides[sym]
    if sym in _DEFAULT_BASES:
        return _DEFAULT_BASES[sym]
    if sym == "BTC/USDT":
        return default_base
    return _hash_base(sym)


def synthetic_price(base: float, ts: int, amplitude: float = 0.02) -> float:
    """Price oscillating ±``amplitude`` over a 1h cycle. Pure in ``(base, ts)``."""
    return base * (1 + amplitude * math.sin(2 * math.pi * ts / 3600))


def synthetic_ticker(symbol: str, base: float, ts: int) -> Dict[str, Any]:
    price = synthetic_price(base, ts)
    return {
        "symbol": symbol,
        "last": price,
        "close": price,
        "bid": price * 0.999,
        "ask": price * 1.001,
        "timestamp": ts * 1000,
        "info": {"dry_run": True},
    }


def synthetic_ohlcv(base: float, ts: int, timeframe: str = "1h", limit: int = 100) -> List[List[float]]:
    tf = timeframe_seconds(timeframe)
    candles: List[List[float]] = []
    for i in range(limit):
        bucket = ts - (limit - 1 - i) * tf
        close = synthetic_price(base, bucket)
        open_ = synthetic_price(base, bucket - tf)
        high = max(open_, close) * 1.001
        low = min(open_, close) * 0.999
        candles.append([bucket * 1000, open_, high, low, close, 1.0])
    return candles


def synthetic_order_book(symbol: str, base: float, ts: int, limit: int = 20) -> Dict[str, Any]:
    price = synthetic_price(base, ts)
    bids = [[price * (1 - 0.0001 * (i + 1)), 1.0] for i in range(limit)]
    asks = [[price * (1 + 0.0001 * (i + 1)), 1.0] for i in range(limit)]
    return {
        "symbol": symbol,
        "bids": bids,
        "asks": asks,
        "timestamp": ts * 1000,
        "info": {"dry_run": True},
    }


__all__ = [
    "synthetic_price",
    "synthetic_ticker",
    "synthetic_ohlcv",
    "synthetic_order_book",
    "timeframe_seconds",
    "base_price_for",
    "parse_base_prices",
]
