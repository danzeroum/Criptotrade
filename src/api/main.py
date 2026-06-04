"""FastAPI gateway — Criptotrade API v1.

Phase 1 surface: /health, /v1/metrics, /v1/hitl/config, /v1/alerts (+ history).
Orders/positions/agents arrive in later phases.
"""
from __future__ import annotations

import os
import secrets
from typing import Set

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.routes import alerts, hitl, metrics

PREFIX = "/v1"
PUBLIC_PATHS: Set[str] = {
    "/health",
    "/v1/docs",
    "/v1/redoc",
    "/openapi.json",
}


def _valid_keys() -> Set[str]:
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


def create_app() -> FastAPI:
    app = FastAPI(
        title="Criptotrade API",
        description="Gateway de orquestração de trading com agentes AI.",
        version="1.0.0",
        docs_url="/v1/docs",
        redoc_url="/v1/redoc",
    )

    app.add_middleware(APIKeyMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:8501").split(","),
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["X-API-Key", "Content-Type"],
    )

    app.include_router(metrics.router, prefix=PREFIX)
    app.include_router(hitl.router, prefix=PREFIX)
    app.include_router(alerts.router, prefix=PREFIX)

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

    @app.exception_handler(404)
    async def not_found(request: Request, exc):
        return JSONResponse(
            status_code=404,
            content={
                "error": "not_found",
                "message": f"O recurso '{request.url.path}' não existe nesta API.",
                "docs": "/v1/docs",
            },
        )

    return app


app = create_app()
