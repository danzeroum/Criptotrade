"""A5 exchange-client factory: DB-managed connection first, env fallback.

Both processes (API via ``deps.get_exchange_client`` and the orchestrator
loop) build their client HERE, so the live-routing gate runs at startup of
each one:

* An ACTIVE, non-revoked connection in ``exchange_connections`` wins — its
  credentials/exchange/testnet are used. With the table empty (every legacy
  deployment), behavior falls back to the env vars bit-for-bit, under any
  AUTH_MODE.
* ``ORDER_ROUTING=live`` is only allowed with an active ``scope=trade``
  connection whose last test PASSED (aceite 3). Anything else refuses to boot
  — fail-loud, mirroring the mandatory EXCHANGE_DRY_RUN. Declared consequence:
  live routing on raw env credentials is no longer possible; the whole point
  of A5 is that the key that can move money is managed, scoped and tested.
* Rotation resets the test status, so a rotated live connection blocks the
  next boot until re-tested (fail-safe by design — the console chains a
  test CTA right after rotating).
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _routing() -> str:
    return (os.getenv("ORDER_ROUTING", "paper") or "paper").strip().lower()


def build_exchange_client():
    from src.core.exchange_client import ExchangeClient  # lazy — ccxt optional in CI

    active = None
    try:
        from src.exchanges.store import ConnectionStore

        active = ConnectionStore().get_active()
    except Exception:  # pragma: no cover - pre-migration db or missing table
        active = None

    live = _routing() == "live"
    if live:
        # Aceite 3: live only with an active, tested, trade-scoped connection.
        if active is None:
            raise RuntimeError(
                "ORDER_ROUTING=live exige uma conexão de exchange ATIVA com escopo"
                " 'trade' e teste ok (tela Conexões & Chaves). Credenciais soltas"
                " por env não habilitam o modo real."
            )
        if active["scope"] != "trade":
            raise RuntimeError(
                f"ORDER_ROUTING=live: a conexão ativa \"{active['label']}\" tem escopo"
                " 'read'. O modo real exige uma conexão com escopo 'trade' testada."
            )
        if not active["last_test_ok"]:
            raise RuntimeError(
                f"ORDER_ROUTING=live: a conexão \"{active['label']}\" ainda não tem um"
                " teste de conexão OK (rotacionou recentemente?). Rode 'Testar"
                " conexão' no console antes de subir o modo real."
            )

    if active is not None:
        from src.exchanges.store import ConnectionStore

        config = ConnectionStore().config(active)
        testnet = bool(active["testnet"])
        if live:
            # Nota 1 da revisão: uma linha inconfundível dizendo PARA ONDE o
            # roteamento real aponta — testnet de staging vs dinheiro de verdade.
            logger.warning(
                "LIVE routing → %s %s (conexão \"%s\")",
                active["exchange_id"].upper(),
                "TESTNET" if testnet else "REAL",
                active["label"],
            )
        return ExchangeClient(
            exchange_id=active["exchange_id"],
            testnet=testnet,
            api_key=config.get("api_key"),
            api_secret=config.get("api_secret"),
        )

    # Legacy env fallback (bit-compatible; only reachable with paper routing).
    return ExchangeClient(
        exchange_id=os.getenv("EXCHANGE", "binance"),
        testnet=os.getenv("EXCHANGE_TESTNET", "true").lower() == "true",
        api_key=os.getenv("EXCHANGE_API_KEY"),
        api_secret=os.getenv("EXCHANGE_API_SECRET"),
    )


__all__ = ["build_exchange_client"]
