"""A5 connection test: real read-only probe, NEVER an order.

``fetch_balance()`` is the canonical private read-only ccxt call — succeeding
proves the key authenticates and can read the account. Trade permission is
detected best-effort from the exchange's account payload (Binance exposes
``info.canTrade``); when the exchange doesn't expose it we say so honestly
("não verificável") instead of guessing. Every error message is passed through
:func:`src.exchanges.store.redact` so credentials never leak into responses,
logs or ledger events (the A5 hard guardrail).
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict

from src.exchanges.store import redact

_TIMEOUT_S = 10.0


def _probe(exchange_id: str, api_key: str, api_secret: str, testnet: bool) -> Dict[str, Any]:
    import ccxt  # lazy: optional in the lean CI

    exchange_class = getattr(ccxt, exchange_id)
    ex = exchange_class({
        "apiKey": api_key,
        "secret": api_secret,
        "enableRateLimit": True,
        "timeout": int(_TIMEOUT_S * 1000),
        "options": {"defaultType": "spot"},
    })
    if testnet and hasattr(ex, "set_sandbox_mode"):
        ex.set_sandbox_mode(True)
    balance = ex.fetch_balance()  # read-only; NEVER place an order here
    info = balance.get("info") if isinstance(balance, dict) else None
    can_trade = info.get("canTrade") if isinstance(info, dict) else None
    return {
        "read_ok": True,
        # True/False when the exchange exposes it; None = not verifiable here.
        "trade_detected": bool(can_trade) if can_trade is not None else None,
    }


async def test_connection(exchange_id: str, config: Dict[str, Any],
                          testnet: bool) -> Dict[str, Any]:
    """Run the probe off-loop with a hard timeout. Returns
    ``{ok, read_ok, trade_detected?, error?}`` — error text always redacted."""
    api_key = config.get("api_key") or ""
    api_secret = config.get("api_secret") or ""
    try:
        detail = await asyncio.wait_for(
            asyncio.to_thread(_probe, exchange_id, api_key, api_secret, testnet),
            timeout=_TIMEOUT_S + 2,
        )
        return {"ok": True, **detail}
    except asyncio.TimeoutError:
        return {"ok": False, "read_ok": False,
                "error": f"Timeout ao contatar {exchange_id} (10s)."}
    except Exception as exc:  # noqa: BLE001 - the operator needs the real reason
        return {"ok": False, "read_ok": False,
                "error": redact(str(exc), api_key, api_secret)[:300]}


__all__ = ["test_connection"]
