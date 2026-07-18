"""/v1/security — A7 self-service: my sessions and my login history.

Strictly scoped to the AUTHENTICATED user (cookie session): machine keys,
demo and anonymous callers get 401 — there is no session to manage and the
login history contains real e-mails/IPs. Another user's session id behaves as
nonexistent (404), never as forbidden, to avoid leaking that it exists.
IP allowlisting is deliberately deferred (declared in the 5b PR).
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response

from src.api import deps
from src.api.authn import SESSION_COOKIE, clear_session_cookies, get_principal
from src.api.schemas import APIResponse, AuditEventOut, Meta, SessionOut
from src.audit import normalize as audit
from src.auth import security as security_lib

router = APIRouter(prefix="/security", tags=["security"])


def _require_user(request: Request) -> Dict[str, Any]:
    principal = get_principal(request)
    if principal.kind != "user":
        raise HTTPException(status_code=401, detail={
            "error": "unauthorized",
            "message": "Faça login para gerenciar suas sessões.",
            "docs": "/v1/docs",
        })
    user = deps.get_user_store().get(principal.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail={
            "error": "unauthorized", "message": "Sessão inválida.", "docs": "/v1/docs",
        })
    return user


def _current_session_id(request: Request, sessions: List[Dict[str, Any]]) -> str | None:
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token:
        return None
    th = security_lib.hash_token(token)
    for s in sessions:
        if s["token_hash"] == th:
            return s["id"]
    return None


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _audit_event(event: str, user: Dict[str, Any], request: Request, detail: str) -> None:
    deps.get_ledger().log_auth_event(
        event, actor=user["email"], email=user["email"], ip=_client_ip(request),
        user_agent=request.headers.get("user-agent", "")[:300], detail=detail,
    )


@router.get(
    "/sessions",
    response_model=APIResponse[List[SessionOut]],
    summary="Minhas sessões ativas (a atual vem marcada)",
)
async def list_sessions(request: Request) -> APIResponse[List[SessionOut]]:
    user = _require_user(request)
    rows = deps.get_session_store().list_for_user(user["id"])
    current_id = _current_session_id(request, rows)
    return APIResponse(data=[
        SessionOut(
            id=r["id"], created_at=r["created_at"], last_seen_at=r["last_seen_at"],
            ip=r["ip"], user_agent=r["user_agent"], remember=bool(r["remember"]),
            current=(r["id"] == current_id),
        )
        for r in rows
    ])


@router.delete(
    "/sessions/{session_id}",
    response_model=APIResponse[dict],
    summary="Encerra uma das minhas sessões (a atual encerra o login)",
)
async def revoke_session(
    request: Request, response: Response, session_id: str = Path(...),
) -> APIResponse[dict]:
    user = _require_user(request)
    store = deps.get_session_store()
    rows = store.list_for_user(user["id"])
    current_id = _current_session_id(request, rows)
    if not store.revoke_for_user(session_id, user["id"]):
        raise HTTPException(status_code=404, detail={
            "error": "session_not_found",
            "message": "Sessão não encontrada.",
            "docs": "/v1/docs",
        })
    if session_id == current_id:
        clear_session_cookies(response)
    _audit_event("session_revoked", user, request, f"session={session_id}")
    return APIResponse(data={"revoked": True, "current": session_id == current_id})


@router.post(
    "/sessions/revoke-others",
    response_model=APIResponse[dict],
    summary="Encerra todas as minhas sessões exceto a atual",
)
async def revoke_other_sessions(request: Request) -> APIResponse[dict]:
    user = _require_user(request)
    store = deps.get_session_store()
    rows = store.list_for_user(user["id"])
    current_id = _current_session_id(request, rows)
    if current_id is None:
        raise HTTPException(status_code=401, detail={
            "error": "unauthorized", "message": "Sessão inválida.", "docs": "/v1/docs",
        })
    revoked = store.revoke_others(user["id"], current_id)
    _audit_event("sessions_revoked_others", user, request, f"revoked={revoked}")
    return APIResponse(data={"revoked": revoked})


@router.get(
    "/logins",
    response_model=APIResponse[List[AuditEventOut]],
    summary="Meu histórico de logins (sucessos e falhas do MEU e-mail)",
)
async def login_history(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> APIResponse[List[AuditEventOut]]:
    user = _require_user(request)
    # Server-side scoping to the caller's own e-mail: the shared audit trail
    # (A4) is where operador+ sees everyone; this screen never widens.
    total, events = audit.read_audit_page(
        deps.get_ledger(), action="login", actor=user["email"],
        limit=limit, offset=offset,
    )
    return APIResponse(
        data=[AuditEventOut(**e) for e in events],
        meta=Meta(total=total, page=offset // limit + 1, per_page=limit),
    )


__all__ = ["router"]
