"""FastAPI gateway — Criptotrade API v1.

Phase 1 surface: /health, /v1/metrics, /v1/hitl/config, /v1/alerts (+ history).
Orders/positions/agents arrive in later phases.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.routes import (
    account,
    agents,
    alerts,
    audit,
    auth,
    exchanges,
    backtest,
    config,
    hitl,
    journal,
    market,
    metrics,
    notifications,
    onboarding,
    orders,
    process,
    risk,
    security,
    trades,
    users,
)
from src.api.authn import auth_mode, require_principal, resolve_principal
from src.api.observability import PrometheusMiddleware, metrics_response
from src.api.request_id import RequestIdMiddleware
from src.core.db import init_db
from src.core.ratelimit import build_rate_limiter

_log = logging.getLogger(__name__)

PREFIX = "/v1"
PUBLIC_PATHS: set[str] = {
    "/health",
    "/health/ready",
    "/metrics",
    "/v1/docs",
    "/v1/redoc",
    "/v1/openapi.json",
}
# Auth endpoints must be reachable without an API key — the browser has none
# (login/refresh/reset happen BEFORE any credential exists).
PUBLIC_PREFIXES: tuple[str, ...] = ("/v1/auth/",)


def _is_public(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)


def _valid_keys() -> set[str]:
    raw = os.getenv("API_KEYS", "").strip()
    return {k for k in (s.strip() for s in raw.split(",")) if k}


def _enforce_prod_security() -> None:
    """Fail-closed in production: refuse to boot with the security gate open.

    ``APIKeyMiddleware``/CORS are intentionally lenient in dev — no ``API_KEYS``
    means auth is open and ``CORS_ORIGINS`` defaults to ``*`` — so local work and
    the dashboard stay frictionless (P0-1/P0-2). In production those same
    defaults silently disable the protection, so when ``APP_ENV=production`` we
    turn the silent fail-open into a loud fail-closed at startup, mirroring how
    ``ExchangeClient`` refuses to run when ``EXCHANGE_DRY_RUN`` is unset.
    """
    if os.getenv("APP_ENV", "").strip().lower() != "production":
        return
    problems: list[str] = []
    # Session auth (AUTH_MODE=demo/required) also closes the gate — the demo
    # principal is read-only and writes need a real session or an API key.
    if not _valid_keys() and auth_mode() == "off":
        problems.append(
            "API_KEYS must be a non-empty allowlist, or AUTH_MODE must be "
            "'demo'/'required' (auth is fail-open otherwise)"
        )
    origins = {o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")}
    if not origins - {""} or "*" in origins:
        problems.append("CORS_ORIGINS must be an explicit origin allowlist, not '*'")
    if problems:
        raise RuntimeError(
            "Refusing to start the API in production with an open security gate — "
            + "; ".join(problems)
            + ". Set these in the deploy env (see .env.prod.example), or unset "
            "APP_ENV outside production."
        )


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Resolve the request principal; legacy X-API-Key gate under AUTH_MODE=off.

    A1 turns this from a reject-only gate into a *resolver*: every request gets
    a ``request.state.principal`` (machine via ``X-API-Key``, user via session
    cookie, demo/anonymous otherwise — see ``src/api/authn.py``). Enforcement
    lives in the ``require_principal`` router dependency. The one legacy
    behavior kept bit-for-bit: under ``AUTH_MODE=off`` with ``API_KEYS`` set,
    requests without a valid key are rejected here exactly as before, so
    existing deployments don't change semantics.
    """

    async def dispatch(self, request: Request, call_next):
        request.state.principal = resolve_principal(request)
        if auth_mode() == "off":
            keys = _valid_keys()
            if keys and not _is_public(request.url.path):
                # A5: a resolved machine principal means the key was valid —
                # either the legacy env allowlist or a DB platform key. The
                # legacy 401 for everything else stays bit-for-bit.
                if request.state.principal.kind != "machine":
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
        # Backend selected from env: Redis (shared across replicas) when REDIS_URL
        # is set, else per-process in-memory. Fails open to in-memory on Redis error.
        self._limiter = build_rate_limiter(self._WINDOW)

    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        is_write = request.method in ("POST", "PATCH", "PUT", "DELETE")
        limit = self._WRITE_LIMIT if is_write else self._READ_LIMIT
        key = f"{ip}:{'w' if is_write else 'r'}"

        if not self._limiter.allow(key, limit):
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
        return await call_next(request)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Apply pending SQLite migrations on startup (idempotent; both processes do it).
    init_db()
    # One-shot first-admin seed from ADMIN_EMAIL/ADMIN_PASSWORD (D3; no-op when
    # the users table already has rows or the envs are unset).
    from src.auth.store import bootstrap_admin
    bootstrap_admin()
    # Mark any backtest jobs still "running" at startup as errored — they were
    # interrupted when the process died and will not be auto-retried.
    from src.api.routes.backtest import _reconcile_orphans
    _reconcile_orphans()
    # A6: background dispatcher tailing alerts.jsonl (the shared meeting point
    # of both processes). Duplicate-safe by design: the cursor is claimed with
    # an optimistic UPDATE, so even N workers yield exactly one delivery.
    # NOTIFY_DISPATCH_INTERVAL_S <= 0 disables the loop.
    import asyncio

    from src.api import deps as _deps

    interval = float(os.getenv("NOTIFY_DISPATCH_INTERVAL_S", "5"))
    stop_event: asyncio.Event | None = None
    task: asyncio.Task | None = None
    if interval > 0:
        _deps.get_dispatcher().ensure_initialized()
        stop_event = asyncio.Event()

        async def _notify_loop() -> None:
            while not stop_event.is_set():
                try:
                    await asyncio.to_thread(_deps.get_dispatcher().dispatch_pending)
                except Exception:  # noqa: BLE001 - the loop must survive anything
                    _log.warning("Notification dispatch pass failed", exc_info=True)
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=interval)
                except asyncio.TimeoutError:
                    pass

        task = asyncio.create_task(_notify_loop())
    yield
    if stop_event is not None:
        stop_event.set()
    if task is not None:
        try:
            await asyncio.wait_for(task, timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            task.cancel()


def _init_sentry() -> None:
    """Initialize Sentry error monitoring when SENTRY_DSN is set (no-op otherwise).

    Sentry's FastAPI integration auto-captures unhandled 5xx exceptions with
    request context. Without a DSN this does nothing — the owner provides
    SENTRY_DSN in production (see docs/acaoPendenteDono.md).
    """
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return
    try:
        import sentry_sdk
    except ImportError:  # pragma: no cover - sentry-sdk is a declared dependency
        _log.warning("SENTRY_DSN is set but sentry-sdk is not installed; skipping.")
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("APP_ENV", "development"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
        send_default_pii=False,
    )
    _log.info("Sentry initialized (environment=%s)", os.getenv("APP_ENV", "development"))


def create_app() -> FastAPI:
    _init_sentry()
    _enforce_prod_security()
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
    cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["X-API-Key", "Content-Type"],
        # Cookies only cross origin when the allowlist is explicit ('*' + creds
        # is invalid per the CORS spec; production is same-origin via /api).
        allow_credentials="*" not in cors_origins,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)
    # Measures total latency incl. the other middleware (and 429s).
    app.add_middleware(PrometheusMiddleware)
    # Outermost: bind a correlation id before anything else runs or logs.
    app.add_middleware(RequestIdMiddleware)

    # Auth endpoints are public by design (the browser has no credential yet).
    app.include_router(auth.router, prefix=PREFIX)
    # Every other router sits behind the principal gate (no-op under
    # AUTH_MODE=off; rejects anonymous under 'required'; CSRF check for
    # cookie-authenticated writes) — see src/api/authn.py.
    guarded = [Depends(require_principal)]
    app.include_router(metrics.router, prefix=PREFIX, dependencies=guarded)
    app.include_router(hitl.router, prefix=PREFIX, dependencies=guarded)
    app.include_router(orders.router, prefix=PREFIX, dependencies=guarded)
    app.include_router(agents.router, prefix=PREFIX, dependencies=guarded)
    app.include_router(process.router, prefix=PREFIX, dependencies=guarded)
    app.include_router(alerts.router, prefix=PREFIX, dependencies=guarded)
    app.include_router(market.router, prefix=PREFIX, dependencies=guarded)
    app.include_router(risk.router, prefix=PREFIX, dependencies=guarded)
    app.include_router(backtest.router, prefix=PREFIX, dependencies=guarded)
    app.include_router(journal.router, prefix=PREFIX, dependencies=guarded)
    app.include_router(config.router, prefix=PREFIX, dependencies=guarded)
    app.include_router(trades.router, prefix=PREFIX, dependencies=guarded)
    # A4: every route additionally requires view_audit (operador+/machine).
    app.include_router(audit.router, prefix=PREFIX, dependencies=guarded)
    # A7: strictly self-service — every route 401s without a user session.
    app.include_router(security.router, prefix=PREFIX, dependencies=guarded)
    # A2: same self-service contract as /v1/security.
    app.include_router(account.router, prefix=PREFIX, dependencies=guarded)
    # A6: channel secrets — every route requires edit_settings (admin).
    app.include_router(notifications.router, prefix=PREFIX, dependencies=guarded)
    # A5: exchange credentials & platform keys — every route requires manage_keys.
    app.include_router(exchanges.router, prefix=PREFIX, dependencies=guarded)
    app.include_router(exchanges.keys_router, prefix=PREFIX, dependencies=guarded)
    # A10: admin-user-only guide (per-route gate inside the module).
    app.include_router(onboarding.router, prefix=PREFIX, dependencies=guarded)
    # A3: per-route manage_users enforcement lives inside the module.
    app.include_router(users.router, prefix=PREFIX)
    app.include_router(users.roles_router, prefix=PREFIX)

    @app.get("/health", tags=["infra"])
    async def health() -> dict:
        return {"status": "healthy", "version": "1.0.0"}

    @app.get("/health/ready", tags=["infra"], include_in_schema=False)
    async def readiness() -> JSONResponse:
        """Readiness probe — the SQLite backend is reachable (503 if not)."""
        try:
            from src.core.db import connection

            with connection() as conn:
                conn.execute("SELECT 1")
        except Exception:  # pragma: no cover - exercised only on a broken DB
            return JSONResponse(
                status_code=503, content={"status": "not_ready", "checks": {"db": "error"}}
            )
        return JSONResponse(content={"status": "ready", "checks": {"db": "ok"}})

    @app.get("/metrics", tags=["infra"], include_in_schema=False)
    async def prometheus_metrics() -> Response:
        """Prometheus exposition endpoint (scraped by the prometheus service)."""
        return metrics_response()

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
