"""/v1/onboarding/status — A10: first-configuration guide (GET/PATCH).

Visible ONLY to an authenticated admin USER: the guide's steps require
``manage_keys``/``edit_settings`` and it configures the SYSTEM, so operador,
visualizador, demo, anonymous and machine keys all get 403 (machines hold
``manage_keys`` but the guide is for humans — declared). New route: no legacy
behavior to preserve under ``AUTH_MODE=off`` (anonymous → 403; console hides
the entry, standard of the previous phases).
"""
from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException, Request

from src.api import deps
from src.api.authn import get_principal
from src.api.schemas import APIResponse, OnboardingPatch, OnboardingStatusOut
from src.onboarding.status import STEP_IDS, OnboardingStore, compute_status

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _require_admin_user(request: Request) -> None:
    principal = get_principal(request)
    if principal.kind != "user" or principal.role != "admin":
        raise HTTPException(status_code=403, detail={
            "error": "forbidden",
            "message": "O guia de configuração é exclusivo do Admin autenticado.",
            "required_permission": "manage_keys",
        })


def _summary() -> Dict[str, Any]:
    """The Review step's honest snapshot — computed from the REAL stores, never
    an echo of what the wizard thinks happened."""
    connection = None
    try:
        active = deps.get_connection_store().get_active()
        if active is not None:
            connection = {
                "label": active["label"], "exchange": active["exchange_id"],
                "scope": active["scope"], "testnet": bool(active["testnet"]),
                "tested_ok": bool(active["last_test_ok"]),
            }
    except Exception:  # pragma: no cover - pre-migration db
        connection = None

    risk: Dict[str, Any] = {}
    try:
        from src.api.routes.risk import _load_yaml

        cfg = _load_yaml()
        risk = {
            "max_position_size_pct": cfg.get("position_limits", {})
                .get("max_position_size_pct", 5.0),
            "max_daily_loss_pct": cfg.get("loss_limits", {})
                .get("max_daily_loss_pct", 5.0),
        }
    except Exception:  # pragma: no cover - unreadable config file
        risk = {}

    dry_run_raw = os.getenv("EXCHANGE_DRY_RUN")
    return {
        "connection": connection,
        "routing": (os.getenv("ORDER_ROUTING", "paper") or "paper").strip().lower(),
        "dry_run": None if dry_run_raw is None else dry_run_raw.lower() == "true",
        "autonomy_level": deps.get_hitl_store().level,
        "risk": risk,
        "pairs": os.getenv("SYMBOLS", "BTC/USDT"),
        "initial_capital": float(os.getenv("INITIAL_CAPITAL", "10000") or 10000),
    }


@router.get("/status", response_model=APIResponse[OnboardingStatusOut],
            summary="Status do guia (passos derivados do estado REAL do sistema)")
async def get_status(request: Request) -> APIResponse[OnboardingStatusOut]:
    _require_admin_user(request)
    status = compute_status(deps.get_ledger(), deps.get_connection_store())
    status["summary"] = _summary()
    return APIResponse(data=OnboardingStatusOut(**status))


@router.patch("/status", response_model=APIResponse[OnboardingStatusOut],
              summary="Marca pular/concluir um passo, ou dispensa o guia")
async def patch_status(
    request: Request, body: OnboardingPatch = Body(...),
) -> APIResponse[OnboardingStatusOut]:
    _require_admin_user(request)
    store = OnboardingStore()
    state = store.load()
    if body.step is not None:
        if body.step not in STEP_IDS:
            raise HTTPException(status_code=422, detail={
                "error": "validation_error",
                "message": f"Passo desconhecido. Use um de: {', '.join(STEP_IDS)}.",
                "field": "step", "docs": "/v1/docs",
            })
        if body.action == "skip":
            if body.step not in state["skipped"]:
                state["skipped"].append(body.step)
            state["completed_manual"] = [s for s in state["completed_manual"]
                                         if s != body.step]
        elif body.action == "complete":
            if body.step not in state["completed_manual"]:
                state["completed_manual"].append(body.step)
            state["skipped"] = [s for s in state["skipped"] if s != body.step]
        else:
            raise HTTPException(status_code=422, detail={
                "error": "validation_error",
                "message": "Informe action ('complete' ou 'skip') junto com step.",
                "field": "action", "docs": "/v1/docs",
            })
    if body.dismiss is not None:
        state["dismissed"] = body.dismiss
    store.save(state)
    status = compute_status(deps.get_ledger(), deps.get_connection_store(), store)
    status["summary"] = _summary()
    return APIResponse(data=OnboardingStatusOut(**status))


__all__ = ["router"]
