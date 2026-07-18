"""Prometheus instrumentation for the API (scale-ready observability).

Exposes ``GET /metrics`` (Prometheus exposition format) and a middleware that
records request counts and latency. Labels use the **route template** (e.g.
``/v1/orders``) rather than the raw path, so cardinality stays bounded even under
arbitrary 404 paths.
"""
from __future__ import annotations

import time

from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Counter, Histogram, generate_latest
from prometheus_client.core import GaugeMetricFamily
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency (seconds)",
    ["method", "path"],
)


def _route_template(request: Request) -> str:
    """Bounded path label: the matched route template, else 'other' (unmatched)."""
    route = request.scope.get("route")
    return getattr(route, "path", None) or "other"


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Record request count + latency for every request (outermost middleware)."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        path = _route_template(request)
        REQUESTS.labels(request.method, path, str(response.status_code)).inc()
        LATENCY.labels(request.method, path).observe(elapsed)
        return response


def metrics_response() -> Response:
    """Render the Prometheus exposition payload for the default registry."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _default_ledger():
    from src.core.ledger import TradingLedger

    return TradingLedger()


class DomainMetricsCollector:
    """Expose trading-domain gauges on /metrics by reading the shared ledger.

    Cross-process-correct: domain state lives in the ledger/DB, so reading it on
    each scrape reflects what the orchestrator (a *separate* process) did — plain
    process-local counters in the API could not. Fail-safe: on any error it emits
    nothing rather than breaking the scrape.
    """

    def __init__(self, ledger_factory=None) -> None:
        self._ledger_factory = ledger_factory or _default_ledger

    def collect(self):
        try:
            from src.core.metrics import PortfolioMetricsCalculator
            from src.orchestration.position_store import PositionStore

            ledger = self._ledger_factory()
            data = PortfolioMetricsCalculator(ledger).compute(period="all").to_dict()
            # Current open positions come from the operational store (the persisted
            # `open_positions` projection), not the historical fill replay in `data`.
            open_positions = PositionStore(lambda: ledger.db_path).count()
        except Exception:  # pragma: no cover - scrape must never raise
            return
        gauges = (
            ("criptotrade_open_positions", "Open paper positions", open_positions),
            ("criptotrade_total_trades", "Closed trades (all time)", data.get("total_trades")),
            ("criptotrade_portfolio_value_usdt", "Portfolio value (USDT)", data.get("portfolio_value_usdt")),
            ("criptotrade_realized_pnl_usdt", "Realised P&L all time (USDT)", data.get("pnl_period_usdt")),
            ("criptotrade_win_rate", "Win rate (0-1)", data.get("win_rate")),
            ("criptotrade_sharpe_ratio", "Sharpe ratio (annualised)", data.get("sharpe_ratio")),
        )
        for name, doc, value in gauges:
            if value is not None:
                yield GaugeMetricFamily(name, doc, value=float(value))


# Register the domain collector once (idempotent across re-imports).
_DOMAIN_COLLECTOR = DomainMetricsCollector()
try:
    REGISTRY.register(_DOMAIN_COLLECTOR)
except ValueError:  # pragma: no cover - already registered
    pass


__all__ = [
    "PrometheusMiddleware",
    "metrics_response",
    "DomainMetricsCollector",
    "REQUESTS",
    "LATENCY",
]
