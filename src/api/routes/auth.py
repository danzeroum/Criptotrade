"""Authentication endpoints (A1): login, 2FA, refresh, logout, recovery, me.

Design notes
------------
* Sessions are httpOnly cookies over server-side rows (see ``src/api/authn.py``
  for why cookies: the alerts SSE cannot send headers). Every mutation here
  writes an ``auth_*`` event to the ledger — the A4 audit-trail feed.
* Anti-enumeration: login and forgot-password return identical responses for
  unknown email, wrong password and suspended accounts, and login runs a
  constant-work argon2 verify either way.
* 2FA challenges are held in a module-level TTL dict — correct for the current
  single-process API container; move to the DB if the API ever runs replicated.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, Response

from src.api import deps
from src.api.authn import (
    REFRESH_COOKIE, SESSION_COOKIE, auth_mode, clear_session_cookies,
    get_principal, set_session_cookies,
)
from src.api.schemas import (
    APIResponse, AuthUserOut, ForgotPasswordIn, LoginIn, MeOut, ResetPasswordIn,
    TwoFactorDisableIn, TwoFactorEnableIn, TwoFactorVerifyIn,
)
from src.auth import security
from src.core.ratelimit import build_rate_limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Login throttle (D2): sliding 15-min window, keyed per-IP AND per-email.
_LOGIN_WINDOW_S = 15 * 60
_LOGIN_IP_LIMIT = 10
_LOGIN_EMAIL_LIMIT = 5
_login_limiter = build_rate_limiter(_LOGIN_WINDOW_S)


def reset_login_limiter() -> None:
    """Rebuild the login limiter (tests; module-level state persists otherwise)."""
    global _login_limiter
    _login_limiter = build_rate_limiter(_LOGIN_WINDOW_S)

# Pending 2FA challenges: token-hash -> (user_id, expires_monotonic, remember).
_CHALLENGE_TTL_S = 5 * 60
_challenges: Dict[str, tuple] = {}

_GENERIC_LOGIN_ERROR = {
    "error": "unauthorized",
    "message": "Credenciais inválidas.",
    "docs": "/v1/docs",
}


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _user_agent(request: Request) -> str:
    return request.headers.get("user-agent", "")[:300]


def _auth_user_out(user: Dict[str, Any]) -> AuthUserOut:
    return AuthUserOut(
        id=user["id"], email=user["email"], name=user.get("name"),
        role=user["role"], totp_enabled=bool(user.get("totp_enabled")),
    )


def _issue_session(response: Response, request: Request, user: Dict[str, Any],
                   *, remember: bool) -> None:
    sessions = deps.get_session_store()
    tokens = sessions.create(
        user["id"], remember=remember, ip=_client_ip(request),
        user_agent=_user_agent(request),
    )
    set_session_cookies(response, request, tokens, remember=remember)
    deps.get_user_store().touch_login(user["id"])


def _prune_challenges() -> None:
    now = time.monotonic()
    for key in [k for k, (_, exp, _r) in _challenges.items() if exp < now]:
        _challenges.pop(key, None)


@router.post("/login", response_model=APIResponse[dict])
async def login(body: LoginIn, request: Request, response: Response) -> APIResponse[dict]:
    ip = _client_ip(request)
    email = body.email.strip().lower()
    if not (_login_limiter.allow(f"login:ip:{ip}", _LOGIN_IP_LIMIT)
            and _login_limiter.allow(f"login:email:{email}", _LOGIN_EMAIL_LIMIT)):
        raise HTTPException(status_code=429, detail={
            "error": "rate_limited",
            "message": "Muitas tentativas. Tente novamente em alguns minutos.",
        })

    ledger = deps.get_ledger()
    user = deps.get_user_store().verify_login(email, body.password)
    if user is None:
        ledger.log_auth_event("login", actor=email, email=email, ip=ip,
                              user_agent=_user_agent(request), success=False)
        raise HTTPException(status_code=401, detail=_GENERIC_LOGIN_ERROR)

    if user.get("totp_enabled"):
        _prune_challenges()
        challenge = security.new_token()
        _challenges[security.hash_token(challenge)] = (
            user["id"], time.monotonic() + _CHALLENGE_TTL_S, body.remember,
        )
        return APIResponse(data={"two_factor_required": True, "challenge": challenge})

    _issue_session(response, request, user, remember=body.remember)
    ledger.log_auth_event("login", actor=user["email"], email=user["email"], ip=ip,
                          user_agent=_user_agent(request), success=True)
    return APIResponse(data={"user": _auth_user_out(user).model_dump()})


@router.post("/2fa/verify", response_model=APIResponse[dict])
async def two_factor_verify(body: TwoFactorVerifyIn, request: Request,
                            response: Response) -> APIResponse[dict]:
    _prune_challenges()
    entry = _challenges.pop(security.hash_token(body.challenge), None)
    if entry is None:
        raise HTTPException(status_code=401, detail=_GENERIC_LOGIN_ERROR)
    user_id, _expires, remember = entry
    users = deps.get_user_store()
    user = users.get(user_id)
    if user is None or user["status"] != "active":
        raise HTTPException(status_code=401, detail=_GENERIC_LOGIN_ERROR)

    secret = security.decrypt_totp_secret(user.get("totp_secret_enc") or "")
    backup_used = False
    if secret and security.verify_totp(secret, body.code):
        pass
    else:
        import json as _json

        hashes = _json.loads(user.get("backup_codes") or "[]")
        remaining = security.consume_backup_code(hashes, body.code)
        if remaining is None:
            # Re-arm the challenge so a typo doesn't force a full re-login.
            _challenges[security.hash_token(body.challenge)] = entry
            raise HTTPException(status_code=401, detail={
                "error": "unauthorized", "message": "Código inválido.",
            })
        users.update_backup_codes(user_id, remaining)
        backup_used = True

    _issue_session(response, request, user, remember=remember or body.remember)
    deps.get_ledger().log_auth_event(
        "login", actor=user["email"], email=user["email"], ip=_client_ip(request),
        user_agent=_user_agent(request), success=True,
        detail="2fa_backup_code" if backup_used else "2fa_totp",
    )
    payload: Dict[str, Any] = {"user": _auth_user_out(user).model_dump()}
    if backup_used:
        import json as _json

        payload["backup_code_used"] = True
        payload["remaining"] = len(_json.loads(users.get(user_id)["backup_codes"] or "[]"))
    return APIResponse(data=payload)


@router.post("/refresh", response_model=APIResponse[dict])
async def refresh(request: Request, response: Response) -> APIResponse[dict]:
    token = request.cookies.get(REFRESH_COOKIE, "")
    if not token:
        raise HTTPException(status_code=401, detail=_GENERIC_LOGIN_ERROR)
    sessions = deps.get_session_store()
    rotated = sessions.rotate(token, ip=_client_ip(request), user_agent=_user_agent(request))
    if rotated is None:
        clear_session_cookies(response)
        raise HTTPException(status_code=401, detail=_GENERIC_LOGIN_ERROR)
    if "__reuse__" in rotated:  # rotated-then-reused refresh: family revoked
        deps.get_ledger().log_auth_event(
            "session_refresh_reuse", actor="unknown", ip=_client_ip(request),
            user_agent=_user_agent(request), success=False,
            detail=f"family={rotated['__reuse__']}",
        )
        clear_session_cookies(response)
        raise HTTPException(status_code=401, detail=_GENERIC_LOGIN_ERROR)
    user = deps.get_user_store().get(rotated["user_id"])
    if user is None or user["status"] != "active":
        clear_session_cookies(response)
        raise HTTPException(status_code=401, detail=_GENERIC_LOGIN_ERROR)
    remember = False  # rotation preserves the stored remember flag server-side
    set_session_cookies(response, request, rotated, remember=remember)
    return APIResponse(data={"user": _auth_user_out(user).model_dump()})


@router.post("/logout", response_model=APIResponse[dict])
async def logout(request: Request, response: Response) -> APIResponse[dict]:
    token = request.cookies.get(SESSION_COOKIE, "")
    principal = get_principal(request)
    if token:
        deps.get_session_store().revoke_by_token(token)
    clear_session_cookies(response)
    deps.get_ledger().log_auth_event(
        "logout", actor=principal.actor, ip=_client_ip(request),
        user_agent=_user_agent(request),
    )
    return APIResponse(data={"logged_out": True})


@router.post("/password/forgot", response_model=APIResponse[dict])
async def forgot_password(body: ForgotPasswordIn, request: Request) -> APIResponse[dict]:
    email = body.email.strip().lower()
    users = deps.get_user_store()
    user = users.get_by_email(email)
    if user is not None and user["status"] == "active":
        token = users.create_reset(user["id"])
        base_url = os.getenv("APP_URL", "").rstrip("/") or "https://criptotrade.buildtovalue.cloud"
        from src.auth.emails import EmailSender

        EmailSender().send_password_reset(email, f"{base_url}/#reset/{token}")
        deps.get_ledger().log_auth_event(
            "password_reset_requested", actor=email, email=email,
            ip=_client_ip(request), user_agent=_user_agent(request),
        )
    # Identical response whether or not the account exists.
    return APIResponse(data={"message": "Se o e-mail existir, enviamos instruções."})


@router.post("/password/reset", response_model=APIResponse[dict])
async def reset_password(body: ResetPasswordIn, request: Request) -> APIResponse[dict]:
    users = deps.get_user_store()
    user_id = users.consume_reset(body.token)
    if user_id is None:
        raise HTTPException(status_code=400, detail={
            "error": "invalid_token",
            "message": "Link de redefinição inválido ou expirado.",
        })
    users.set_password(user_id, body.new_password)
    deps.get_session_store().revoke_all_for_user(user_id)
    user = users.get(user_id)
    deps.get_ledger().log_auth_event(
        "password_reset", actor=user["email"] if user else user_id,
        email=user["email"] if user else None,
        ip=_client_ip(request), user_agent=_user_agent(request),
    )
    return APIResponse(data={"message": "Senha redefinida. Faça login."})


@router.get("/me", response_model=APIResponse[MeOut])
async def me(request: Request) -> APIResponse[MeOut]:
    principal = get_principal(request)
    mode = auth_mode()
    if principal.kind == "user":
        user = deps.get_user_store().get(principal.user_id)
        return APIResponse(data=MeOut(
            mode=mode, authenticated=True,
            user=_auth_user_out(user) if user else None,
            permissions=[],  # populated by RBAC (4b)
        ))
    if principal.kind == "demo":
        return APIResponse(data=MeOut(
            mode=mode, authenticated=False,
            user=AuthUserOut(id="demo", email="demo@criptotrade", name="Demo",
                             role="visualizador"),
            permissions=[],
        ))
    return APIResponse(data=MeOut(mode=mode, authenticated=principal.kind == "machine",
                                  permissions=[]))


# ------------------------------------------------------------------- 2FA mgmt
def _require_user(request: Request) -> Dict[str, Any]:
    principal = get_principal(request)
    if principal.kind != "user":
        raise HTTPException(status_code=401, detail={
            "error": "unauthorized",
            "message": "Faça login para gerenciar o 2FA.",
        })
    user = deps.get_user_store().get(principal.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail=_GENERIC_LOGIN_ERROR)
    return user


@router.post("/2fa/setup", response_model=APIResponse[dict])
async def two_factor_setup(request: Request) -> APIResponse[dict]:
    user = _require_user(request)
    secret = security.new_totp_secret()
    deps.get_user_store().set_totp(
        user["id"], security.encrypt_totp_secret(secret), enabled=False,
    )
    return APIResponse(data={
        "secret": secret,
        "otpauth_uri": security.totp_uri(secret, user["email"]),
    })


@router.post("/2fa/enable", response_model=APIResponse[dict])
async def two_factor_enable(body: TwoFactorEnableIn, request: Request) -> APIResponse[dict]:
    user = _require_user(request)
    secret = security.decrypt_totp_secret(user.get("totp_secret_enc") or "")
    if not secret or not security.verify_totp(secret, body.code):
        raise HTTPException(status_code=400, detail={
            "error": "invalid_code", "message": "Código inválido.",
        })
    codes, hashes = security.generate_backup_codes()
    deps.get_user_store().set_totp(
        user["id"], user["totp_secret_enc"], enabled=True, backup_hashes=hashes,
    )
    deps.get_ledger().log_auth_event(
        "2fa_enabled", actor=user["email"], email=user["email"],
        ip=_client_ip(request), user_agent=_user_agent(request),
    )
    return APIResponse(data={"backup_codes": codes})  # shown once


@router.post("/2fa/disable", response_model=APIResponse[dict])
async def two_factor_disable(body: TwoFactorDisableIn, request: Request) -> APIResponse[dict]:
    user = _require_user(request)
    if not security.verify_password(user.get("password_hash"), body.password):
        raise HTTPException(status_code=401, detail=_GENERIC_LOGIN_ERROR)
    deps.get_user_store().set_totp(user["id"], None, enabled=False, backup_hashes=None)
    deps.get_ledger().log_auth_event(
        "2fa_disabled", actor=user["email"], email=user["email"],
        ip=_client_ip(request), user_agent=_user_agent(request),
    )
    return APIResponse(data={"disabled": True})


__all__ = ["router"]
