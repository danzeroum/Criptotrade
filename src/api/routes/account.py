"""/v1/account — A2 self-service: profile, password, preferences.

Same discipline as /v1/security (A7): strictly the AUTHENTICATED user
(cookie session) — machine keys, demo and anonymous get 401. E-mail change is
deliberately deferred (login identity; needs a re-verification flow) and an
attempted change is an explicit 422 via ``extra='forbid'``, never a silent
no-op. Theme is out of scope (light-only design system). Avatar image upload
deferred — initials + a token-derived color instead.
"""
from __future__ import annotations

from typing import Any, Dict
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, HTTPException, Request

from src.api import deps
from src.api.routes.security import _client_ip, _current_session_id, _require_user
from src.api.schemas import (
    APIResponse, PasswordChangeIn, PreferencesOut, PreferencesPatch,
    ProfileOut, ProfilePatch,
)
from src.auth import security as security_lib

router = APIRouter(prefix="/account", tags=["account"])

# Avatar palette derives 1:1 from the design-system accent/neutral tokens
# (styles.css) — token ids, never new hex. The console maps id → var(--<id>).
AVATAR_COLORS = ("ink", "ink-2", "info", "violet", "up", "down", "warn")

DEFAULT_PREFS: Dict[str, str] = {
    "locale": "pt-BR",        # UI language (formatting now; string i18n later)
    "timezone": "auto",       # 'auto' = browser timezone (today's behavior)
    "number_locale": "auto",  # 'auto' = en-US convention (M7 canonical)
    "date_locale": "auto",    # 'auto' = pt-BR (today's behavior)
}


def _audit(event: str, user: Dict[str, Any], request: Request, detail: str | None = None) -> None:
    deps.get_ledger().log_auth_event(
        event, actor=user["email"], email=user["email"], ip=_client_ip(request),
        user_agent=request.headers.get("user-agent", "")[:300], detail=detail,
    )


def _profile_out(user: Dict[str, Any]) -> ProfileOut:
    return ProfileOut(
        id=user["id"], email=user["email"], name=user.get("name"),
        job_title=user.get("job_title"), avatar_color=user.get("avatar_color"),
        role=user["role"], totp_enabled=bool(user.get("totp_enabled")),
        created_at=user.get("created_at"),
    )


@router.get("/profile", response_model=APIResponse[ProfileOut],
            summary="Meu perfil (e-mail é somente leitura)")
async def get_profile(request: Request) -> APIResponse[ProfileOut]:
    return APIResponse(data=_profile_out(_require_user(request)))


@router.patch("/profile", response_model=APIResponse[ProfileOut],
              summary="Atualiza nome/cargo/cor do avatar (e-mail não muda aqui)")
async def patch_profile(
    request: Request, patch: ProfilePatch = Body(...),
) -> APIResponse[ProfileOut]:
    user = _require_user(request)
    updates = patch.model_dump(exclude_none=True)
    if "avatar_color" in updates and updates["avatar_color"] not in AVATAR_COLORS:
        raise HTTPException(status_code=422, detail={
            "error": "validation_error",
            "message": f"Cor de avatar inválida. Use uma de: {', '.join(AVATAR_COLORS)}.",
            "field": "avatar_color", "docs": "/v1/docs",
        })
    if updates:
        deps.get_user_store().update_profile(user["id"], **updates)
        _audit("profile_updated", user, request, detail=", ".join(sorted(updates)))
    return APIResponse(data=_profile_out(deps.get_user_store().get(user["id"])))


@router.patch("/password", response_model=APIResponse[dict],
              summary="Troca a senha (exige a atual; desconecta as outras sessões)")
async def change_password(
    request: Request, body: PasswordChangeIn = Body(...),
) -> APIResponse[dict]:
    user = _require_user(request)
    if not security_lib.verify_password(user.get("password_hash"), body.current_password):
        raise HTTPException(status_code=401, detail={
            "error": "unauthorized", "message": "Credenciais inválidas.",
            "docs": "/v1/docs",
        })
    users = deps.get_user_store()
    users.set_password(user["id"], body.new_password)
    # A7 integration: a password change is a "was my account compromised?"
    # moment — every OTHER session dies; the one making the change survives.
    sessions = deps.get_session_store()
    current_id = _current_session_id(request, sessions.list_for_user(user["id"]))
    revoked = (sessions.revoke_others(user["id"], current_id)
               if current_id else 0)
    _audit("password_changed", user, request, detail=f"sessions_revoked={revoked}")
    return APIResponse(data={"changed": True, "other_sessions_revoked": revoked})


@router.get("/preferences", response_model=APIResponse[PreferencesOut],
            summary="Minhas preferências de idioma/fuso/formato")
async def get_preferences(request: Request) -> APIResponse[PreferencesOut]:
    user = _require_user(request)
    prefs = {**DEFAULT_PREFS, **deps.get_user_store().get_prefs(user["id"])}
    return APIResponse(data=PreferencesOut(**prefs))


@router.patch("/preferences", response_model=APIResponse[PreferencesOut],
              summary="Atualiza preferências (refletem em todo o console)")
async def patch_preferences(
    request: Request, patch: PreferencesPatch = Body(...),
) -> APIResponse[PreferencesOut]:
    user = _require_user(request)
    updates = patch.model_dump(exclude_none=True)
    if "timezone" in updates and updates["timezone"] != "auto":
        try:
            ZoneInfo(updates["timezone"])
        except Exception:
            raise HTTPException(status_code=422, detail={
                "error": "validation_error",
                "message": "Fuso horário inválido — use um identificador IANA (ex.: America/Sao_Paulo).",
                "field": "timezone", "docs": "/v1/docs",
            })
    users = deps.get_user_store()
    merged = {**DEFAULT_PREFS, **users.get_prefs(user["id"]), **updates}
    users.set_prefs(user["id"], merged)
    return APIResponse(data=PreferencesOut(**merged))


__all__ = ["router", "AVATAR_COLORS", "DEFAULT_PREFS"]
