"""Prometheus instrumentation for the API (scale-ready observability).

Exposes ``GET /metrics`` (Prometheus exposition format) and a middleware that
records request counts and latency. Labels use the **route template** (e.g.
``/v1/orders``) rather than the raw path, so cardinality stays bounded even under
arbitrary 404 paths.
"""
from __future__ import annotations

import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
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


__all__ = ["PrometheusMiddleware", "metrics_response", "REQUESTS", "LATENCY"]
