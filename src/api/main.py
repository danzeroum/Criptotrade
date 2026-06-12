"""FastAPI gateway — Criptotrade API v1.

Phase 1 surface: /health, /v1/metrics, /v1/hitl/config, /v1/alerts (+ history).
Orders/positions/agents arrive in later phases.
"""
from __future__ import annotations

import logging
import os
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.routes import (
    agents,
    alerts,
    backtest,
    config,
    hitl,
    journal,
    market,
    metrics,
    orders,
    process,
    risk,
)
from src.core.db import init_db

_log = logging.getLogger(__name__)

PREFIX = "/v1"
PUBLIC_PATHS: set[str] = {
    "/health",
    "/v1/docs",
    "/v1/redoc",
    "/v1/openapi.json",
}


def _valid_keys() -> set[str]:
    raw = os.getenv("API_KEYS", "").strip()
    return {k for k in (s.strip() for s in raw.split(",")) if k}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Require ``X-API-Key`` when keys are configured.

    Lenient by design: if ``API_KEYS`` is unset/empty the API is open. This keeps
    local dev and the dashboard frictionless while allowing auth in shared/staging
    deployments simply by setting the env var.
    """

    async def dispatch(self, request: Request, call_next):
        keys = _valid_keys()
        if not keys or request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        provided = request.headers.get("X-API-Key", "")
        if not any(secrets.compare_digest(provided, k) for k in keys):
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "Header 'X-API-Key' ausente ou inválido.",
                    "docs": "/v1/docs",
                },
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add OWASP-recommended security headers to every response (P0-5)."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; object-src 'none'",
        )
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin"
        # XSS auditor is deprecated; CSP is the modern replacement.
        response.headers["X-XSS-Protection"] = "0"
        # Short max-age here; nginx/load-balancer should set a longer value in prod.
        response.headers["Strict-Transport-Security"] = "max-age=300"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP sliding-window rate limiting (P0-3).

    Write methods (POST, PATCH): 30 req/min.
    All other requests: 200 req/min.
    Limits are intentionally relaxed in tests by setting low _WRITE_LIMIT on
    the class before creating the app (or by injecting a patched instance).
    """

    _WRITE_LIMIT: int = 30
    _READ_LIMIT: int = 200
    _WINDOW: float = 60.0

    def __init__(self, app) -> None:
        super().__init__(app)
        self._buckets: dict[tuple, list[float]] = {}

    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        is_write = request.method in ("POST", "PATCH", "PUT", "DELETE")
        limit = self._WRITE_LIMIT if is_write else self._READ_LIMIT
        key = (ip, "w" if is_write else "r")

        now = time.monotonic()
        cutoff = now - self._WINDOW
        bucket = [t for t in self._buckets.get(key, []) if t > cutoff]

        if len(bucket) >= limit:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Muitas requisições. Aguarde e tente novamente.",
                    "retry_after": 60,
                    "docs": "/v1/docs",
                },
                headers={"Retry-After": "60"},
            )

        bucket.append(now)
        self._buckets[key] = bucket
        return await call_next(request)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Apply pending SQLite migrations on startup (idempotent; both processes do it).
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Criptotrade API",
        description="Gateway de orquestração de trading com agentes AI.",
        version="1.0.0",
        docs_url="/v1/docs",
        redoc_url="/v1/redoc",
        openapi_url="/v1/openapi.json",
        lifespan=_lifespan,
    )

    app.add_middleware(APIKeyMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["X-API-Key", "Content-Type"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)

    app.include_router(metrics.router, prefix=PREFIX)
    app.include_router(hitl.router, prefix=PREFIX)
    app.include_router(orders.router, prefix=PREFIX)
    app.include_router(agents.router, prefix=PREFIX)
    app.include_router(process.router, prefix=PREFIX)
    app.include_router(alerts.router, prefix=PREFIX)
    app.include_router(market.router, prefix=PREFIX)
    app.include_router(risk.router, prefix=PREFIX)
    app.include_router(backtest.router, prefix=PREFIX)
    app.include_router(journal.router, prefix=PREFIX)
    app.include_router(config.router, prefix=PREFIX)

    @app.get("/health", tags=["infra"])
    async def health() -> dict:
        return {"status": "healthy", "version": "1.0.0"}

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        loc = first.get("loc", [])
        field = str(loc[-1]) if loc else None
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "message": first.get("msg", "Invalid request"),
                "field": field,
                "docs": "/v1/docs",
            },
        )

    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        # Route-level HTTPException(detail={...}) passes its structured body through.
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        if exc.status_code == 404:
            return JSONResponse(
                status_code=404,
                content={
                    "error": "not_found",
                    "message": f"O recurso '{request.url.path}' não existe nesta API.",
                    "docs": "/v1/docs",
                },
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "http_error", "message": str(exc.detail), "docs": "/v1/docs"},
        )

    # Register for both FastAPI's and Starlette's HTTPException (route-raised vs
    # framework-raised, e.g. unmatched paths) so detail handling is consistent.
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        _log.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": "Erro interno inesperado. Consulte os logs do servidor.",
                "docs": "/v1/docs",
            },
        )

    return app


app = create_app()
