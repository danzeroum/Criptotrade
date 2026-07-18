"""Principal resolution + enforcement for the API (A1/D4).

One request → one ``Principal``:
- valid ``X-API-Key``      → machine principal (orchestrator/integrations),
- valid ``ct_session``     → user principal (cookie, server-side session),
- neither                  → what ``AUTH_MODE`` says:
    off      → anonymous passes (legacy behavior, default),
    demo     → synthetic read-only visualizador (public demo, D5),
    required → anonymous is rejected by ``require_principal``.

Cookies are httpOnly+SameSite=Lax (CSRF: cross-site POSTs don't carry them, and
cookie-authenticated writes must be ``application/json`` — HTML forms can't
produce that cross-origin without a CORS preflight, and CORS stays locked).
"""
from __future__ import annotations

import os
import secrets as _secrets
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Request, Response

SESSION_COOKIE = "ct_session"
REFRESH_COOKIE = "ct_refresh"


def auth_mode() -> str:
    mode = os.getenv("AUTH_MODE", "off").strip().lower()
    return mode if mode in {"off", "demo", "required"} else "off"


def _valid_api_keys() -> set[str]:
    raw = os.getenv("API_KEYS", "").strip()
    return {k for k in (s.strip() for s in raw.split(",")) if k}


@dataclass(frozen=True)
class Principal:
    kind: str          # "machine" | "user" | "demo" | "anonymous"
    actor: str         # audit identity: email, "api-key", "demo", "anonymous"
    role: str          # "admin" | "operador" | "visualizador" | "anonymous"
    user_id: Optional[str] = None

    @property
    def authenticated(self) -> bool:
        return self.kind in {"machine", "user"}


ANONYMOUS = Principal(kind="anonymous", actor="anonymous", role="anonymous")
DEMO = Principal(kind="demo", actor="demo", role="visualizador")
MACHINE = Principal(kind="machine", actor="api-key", role="admin")


def resolve_principal(request: Request) -> Principal:
    """API key first (machines), then session cookie (humans), then AUTH_MODE."""
    provided = request.headers.get("X-API-Key", "")
    if provided:
        for k in _valid_api_keys():
            if _secrets.compare_digest(provided, k):
                return MACHINE

    token = request.cookies.get(SESSION_COOKIE, "")
    if token:
        from src.api import deps  # lazy: avoid import cycle at module load

        session = deps.get_session_store().resolve(token)
        if session is not None:
            user = deps.get_user_store().get(session["user_id"])
            if user is not None and user["status"] == "active":
                return Principal(
                    kind="user", actor=user["email"], role=user["role"],
                    user_id=user["id"],
                )

    return DEMO if auth_mode() == "demo" else ANONYMOUS


def get_principal(request: Request) -> Principal:
    """Read the principal the middleware resolved (fallback: resolve now)."""
    principal = getattr(request.state, "principal", None)
    return principal if principal is not None else resolve_principal(request)


async def require_principal(request: Request) -> Principal:
    """Router-level gate. Anonymous is rejected only under AUTH_MODE=required
    (off keeps today's behavior; demo resolves to a read-only principal)."""
    principal = get_principal(request)
    if auth_mode() == "required" and not principal.authenticated and principal.kind != "demo":
        raise HTTPException(status_code=401, detail={
            "error": "unauthorized",
            "message": "Sessão ausente ou expirada. Faça login.",
            "docs": "/v1/docs",
        })
    # CSRF guard for cookie-authenticated state changes (see module docstring).
    if (
        principal.kind == "user"
        and request.method in {"POST", "PATCH", "PUT", "DELETE"}
        and not (request.headers.get("content-type", "").startswith("application/json"))
    ):
        raise HTTPException(status_code=403, detail={
            "error": "forbidden",
            "message": "Requisições autenticadas por sessão devem usar Content-Type application/json.",
        })
    return principal


# ------------------------------------------------------------------ cookies
def _secure(request: Request) -> bool:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    return proto == "https"


def set_session_cookies(response: Response, request: Request, tokens: dict,
                        *, remember: bool = False) -> None:
    idle_min = int(os.getenv("SESSION_IDLE_TTL_MIN", "30"))
    refresh_days = int(os.getenv("REMEMBER_TTL_D", "30") if remember
                       else os.getenv("REFRESH_TTL_D", "7"))
    secure = _secure(request)
    response.set_cookie(
        SESSION_COOKIE, tokens["token"], httponly=True, samesite="lax",
        secure=secure, path="/", max_age=idle_min * 60,
    )
    response.set_cookie(
        REFRESH_COOKIE, tokens["refresh"], httponly=True, samesite="lax",
        secure=secure, path="/v1/auth/refresh", max_age=refresh_days * 86400,
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/v1/auth/refresh")


__all__ = [
    "Principal", "ANONYMOUS", "DEMO", "MACHINE", "auth_mode",
    "resolve_principal", "get_principal", "require_principal",
    "set_session_cookies", "clear_session_cookies",
    "SESSION_COOKIE", "REFRESH_COOKIE",
]
