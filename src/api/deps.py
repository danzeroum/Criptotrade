"""Dependency providers for the API.

Decoupled from ``src.core.config`` on purpose: importing that module runs
logging setup + ``validate_configuration`` at import time. The API reads the few
env vars it needs directly, keeping startup and tests side-effect-free.
"""
from __future__ import annotations

import os
from functools import lru_cache

from src.agents.registry import AgentRegistry
from src.core.alerts import AlertBus, AlertStore, make_guardrail_sink
from src.core.db import get_db_path
from src.core.ledger import TradingLedger
from src.core.metrics import PortfolioMetricsCalculator
from src.hitl.config import DEFAULT_LEVEL, MAX_LEVEL, MIN_LEVEL, HITLConfigStore, level_info
from src.hitl.orders import OrderStore
from src.safety.guardrails import GuardrailSystem


def _initial_capital() -> float:
    try:
        return float(os.getenv("INITIAL_CAPITAL", "10000"))
    except ValueError:
        return 10_000.0


def _initial_level() -> int:
    raw = os.getenv("AUTONOMY_LEVEL")
    if raw is None:
        return DEFAULT_LEVEL
    try:
        level = int(raw)
    except ValueError:
        return DEFAULT_LEVEL
    return level if MIN_LEVEL <= level <= MAX_LEVEL else DEFAULT_LEVEL


@lru_cache(maxsize=1)
def get_ledger() -> TradingLedger:
    return TradingLedger()


@lru_cache(maxsize=1)
def get_alert_store() -> AlertStore:
    return AlertStore()


@lru_cache(maxsize=1)
def get_alert_bus() -> AlertBus:
    return AlertBus()


@lru_cache(maxsize=1)
def get_hitl_store() -> HITLConfigStore:
    store = HITLConfigStore(get_ledger(), initial_level=_initial_level())
    # Reflect real pending orders (not just open fills) in the HITL snapshot.
    store.pending_orders_provider = get_order_store().pending_count
    return store


@lru_cache(maxsize=1)
def get_order_store() -> OrderStore:
    def _threshold() -> float:
        return level_info(get_hitl_store().level).threshold_usdt

    # Risk gate: guardrail violations are persisted as alerts (in-process sink)
    # and reject the order before any value-threshold auto-approval.
    guardrails = GuardrailSystem(alert_sink=make_guardrail_sink(get_alert_store()))
    return OrderStore(get_ledger(), threshold_provider=_threshold, guardrails=guardrails)


@lru_cache(maxsize=1)
def get_agent_registry() -> AgentRegistry:
    # Cross-process: read cycle counts from the shared SQLite db the loop writes.
    return AgentRegistry(db_path=str(get_db_path()))


@lru_cache(maxsize=1)
def get_exchange_client():  # type: ignore[return]
    from src.core.exchange_client import ExchangeClient  # lazy — ccxt optional in CI
    exchange = os.getenv("EXCHANGE", "binance")
    testnet = os.getenv("EXCHANGE_TESTNET", "true").lower() == "true"
    api_key = os.getenv("EXCHANGE_API_KEY")
    api_secret = os.getenv("EXCHANGE_API_SECRET")
    return ExchangeClient(
        exchange_id=exchange,
        testnet=testnet,
        api_key=api_key,
        api_secret=api_secret,
    )


def get_metrics_calculator() -> PortfolioMetricsCalculator:
    return PortfolioMetricsCalculator(get_ledger(), initial_capital=_initial_capital())


def reset_singletons() -> None:
    """Clear cached singletons (used by tests to inject fresh state)."""
    for fn in (
        get_ledger, get_alert_store, get_alert_bus, get_hitl_store,
        get_order_store, get_agent_registry, get_exchange_client,
    ):
        fn.cache_clear()


__all__ = [
    "get_ledger",
    "get_alert_store",
    "get_alert_bus",
    "get_hitl_store",
    "get_order_store",
    "get_agent_registry",
    "get_metrics_calculator",
    "get_exchange_client",
    "reset_singletons",
]
