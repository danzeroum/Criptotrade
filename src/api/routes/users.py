"""User & role management (A3 RBAC): list, invites, roles, status.

Whole router requires ``manage_users`` (admin-only; the machine principal
deliberately lacks it) except ``GET /roles``, which any authenticated principal
may read (the console renders the permission matrix from it). Every mutation
writes a ledger event — the A4 audit feed. The last active admin can never be
deleted, demoted or suspended (ownership-transfer stand-in).
"""
from __future__ import annotations

import logging
import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api import deps
from src.api.authn import Principal, require_perm, require_principal
from src.api.schemas import (
    APIResponse, InviteCreate, InviteOut, RoleOut, UserOut, UserRolePatch,
    UserStatusPatch,
)
from src.auth.rbac import ROLES, role_matrix

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

_manage = Depends(require_perm("manage_users"))


def _audit(event: str, actor: str, detail: str) -> None:
    deps.get_ledger().log_auth_event(event, actor=actor, detail=detail)


def _guard_last_admin(users, target_user: dict) -> None:
    """Refuse to remove the final active admin from play."""
    if target_user["role"] == "admin" and target_user["status"] == "active" \
            and users.count_active_admins() <= 1:
        raise HTTPException(status_code=409, detail={
            "error": "last_admin",
            "message": "Este é o último Admin ativo — transfira a função antes.",
        })


@router.get("", response_model=APIResponse[List[UserOut]])
async def list_users(principal: Principal = _manage) -> APIResponse[List[UserOut]]:
    users = deps.get_user_store()
    rows = [UserOut(**{**u, "totp_enabled": bool(u.get("totp_enabled"))})
            for u in users.list_users()]
    # Pending invites appear in the same list as status='pending'.
    rows += [
        UserOut(id=f"invite:{i['id']}", email=i["email"], role=i["role"],
                status="pending", invite_id=i["id"], created_at=i["created_at"])
        for i in users.list_invites(pending_only=True)
    ]
    return APIResponse(data=rows)


@router.post("/invite", response_model=APIResponse[InviteOut], status_code=201)
async def invite_user(body: InviteCreate, request: Request,
                      principal: Principal = _manage) -> APIResponse[InviteOut]:
    if body.role not in ROLES:
        raise HTTPException(status_code=422, detail={
            "error": "invalid_role", "message": f"Papel deve ser um de {ROLES}.",
        })
    users = deps.get_user_store()
    email = body.email.strip().lower()
    if users.get_by_email(email) is not None:
        raise HTTPException(status_code=409, detail={
            "error": "already_exists", "message": "Este e-mail já tem conta.",
        })
    token = users.create_invite(email, body.role, invited_by=principal.actor)
    invite = next(i for i in users.list_invites() if i["email"] == email)
    base_url = os.getenv("APP_URL", "").rstrip("/") or "https://criptotrade.buildtovalue.cloud"
    from src.auth.emails import EmailSender

    sender = EmailSender()
    link = f"{base_url}/#invite/{token}"
    try:
        sender.send_password_reset(email, link)  # same transport; link text differs client-side
    except Exception:  # pragma: no cover - mail must not block the invite
        logger.warning("Invite e-mail failed for %s", email, exc_info=True)
    _audit("user_invited", principal.actor, f"{email} as {body.role}")
    return APIResponse(data=InviteOut(id=invite["id"], email=email, role=body.role,
                                      expires_at=invite["expires_at"]))


@router.post("/invites/{invite_id}/resend", response_model=APIResponse[dict])
async def resend_invite(invite_id: str,
                        principal: Principal = _manage) -> APIResponse[dict]:
    users = deps.get_user_store()
    token = users.refresh_invite(invite_id)
    if token is None:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "message": "Convite não encontrado ou já usado.",
        })
    invite = users.get_invite(invite_id)
    base_url = os.getenv("APP_URL", "").rstrip("/") or "https://criptotrade.buildtovalue.cloud"
    from src.auth.emails import EmailSender

    EmailSender().send_password_reset(invite["email"], f"{base_url}/#invite/{token}")
    _audit("user_invite_resent", principal.actor, invite["email"])
    return APIResponse(data={"resent": True})


@router.delete("/invites/{invite_id}", response_model=APIResponse[dict])
async def revoke_invite(invite_id: str,
                        principal: Principal = _manage) -> APIResponse[dict]:
    users = deps.get_user_store()
    invite = users.get_invite(invite_id)
    if invite is None:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "message": "Convite não encontrado.",
        })
    users.revoke_invite(invite_id)
    _audit("user_invite_revoked", principal.actor, invite["email"])
    return APIResponse(data={"revoked": True})


@router.patch("/{user_id}/role", response_model=APIResponse[UserOut])
async def patch_role(user_id: str, body: UserRolePatch,
                     principal: Principal = _manage) -> APIResponse[UserOut]:
    if body.role not in ROLES:
        raise HTTPException(status_code=422, detail={
            "error": "invalid_role", "message": f"Papel deve ser um de {ROLES}.",
        })
    users = deps.get_user_store()
    user = users.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "message": "Usuário não encontrado.",
        })
    if body.role != "admin":
        _guard_last_admin(users, user)
    users.set_role(user_id, body.role)
    _audit("user_role_changed", principal.actor, f"{user['email']}: {user['role']}→{body.role}")
    updated = users.get(user_id)
    return APIResponse(data=UserOut(**{**updated, "totp_enabled": bool(updated.get("totp_enabled"))}))


@router.patch("/{user_id}/status", response_model=APIResponse[UserOut])
async def patch_status(user_id: str, body: UserStatusPatch,
                       principal: Principal = _manage) -> APIResponse[UserOut]:
    if body.status not in {"active", "suspended"}:
        raise HTTPException(status_code=422, detail={
            "error": "invalid_status", "message": "Status deve ser active ou suspended.",
        })
    users = deps.get_user_store()
    user = users.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "message": "Usuário não encontrado.",
        })
    if body.status == "suspended":
        _guard_last_admin(users, user)
        deps.get_session_store().revoke_all_for_user(user_id)  # immediate lockout
    users.set_status(user_id, body.status)
    _audit("user_status_changed", principal.actor, f"{user['email']}: {body.status}")
    updated = users.get(user_id)
    return APIResponse(data=UserOut(**{**updated, "totp_enabled": bool(updated.get("totp_enabled"))}))


@router.delete("/{user_id}", response_model=APIResponse[dict])
async def delete_user(user_id: str,
                      principal: Principal = _manage) -> APIResponse[dict]:
    users = deps.get_user_store()
    user = users.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "message": "Usuário não encontrado.",
        })
    _guard_last_admin(users, user)
    users.delete(user_id)
    _audit("user_deleted", principal.actor, user["email"])
    return APIResponse(data={"deleted": True})


# Spec path is /v1/roles (not /v1/users/roles): separate router, any principal.
roles_router = APIRouter(prefix="/roles", tags=["users"])


@roles_router.get("", response_model=APIResponse[List[RoleOut]],
                  dependencies=[Depends(require_principal)])
async def get_roles() -> APIResponse[List[RoleOut]]:
    return APIResponse(data=[RoleOut(**r) for r in role_matrix()])


__all__ = ["router", "roles_router"]
