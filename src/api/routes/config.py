"""/v1/config — configurações gerais do sistema (env vars + settings).

Leitura e atualização in-memory para o MVP (sem persistência de env).
"""
from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException

from src.agents.registry import AgentRegistry
from src.api.authn import Principal, require_perm
from src.api.deps import get_agent_registry, get_ledger
from src.api.schemas import (
    APIResponse,
    AgentConfigOut,
    AlertsConfigPatch,
    ConfigOut,
    ConfigPatch,
)

router = APIRouter(tags=["config"])


def _log_config_change(actor: str, scope: str, before: Dict[str, Any], after: Dict[str, Any]) -> None:
    """A4: record a config mutation with a before→after diff of changed keys."""
    changed = sorted(k for k in after if after.get(k) != before.get(k))
    if not changed:
        return
    get_ledger().log_decision("config_changed", {
        "actor": actor,
        "scope": scope,
        "before": {k: before.get(k) for k in changed},
        "after": {k: after.get(k) for k in changed},
    })

_runtime_overrides: Dict[str, Any] = {}


def _get_int(key: str, default: int) -> int:
    val = _runtime_overrides.get(key) or os.getenv(key)
    try:
        return int(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def _get_float(key: str, default: float) -> float:
    val = _runtime_overrides.get(key) or os.getenv(key)
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def _get_bool(key: str, default: bool) -> bool:
    val = _runtime_overrides.get(key) or os.getenv(key)
    if val is None:
        return default
    return str(val).lower() in ("true", "1", "yes")


@router.get(
    "/config",
    response_model=APIResponse[ConfigOut],
    summary="Configurações gerais do sistema",
)
async def get_config() -> APIResponse[ConfigOut]:
    return APIResponse(data=ConfigOut(
        exchange=os.getenv("EXCHANGE", "binance"),
        dry_run=_get_bool("EXCHANGE_DRY_RUN", True),
        initial_capital=_get_float("INITIAL_CAPITAL", 10000.0),
        orchestrator_interval_seconds=_get_int("ORCHESTRATOR_INTERVAL_SECONDS", 60),
        autonomy_level=_get_int("AUTONOMY_LEVEL", 2),
        app_env=os.getenv("APP_ENV", "development"),
    ))


@router.patch(
    "/config",
    response_model=APIResponse[ConfigOut],
    summary="Atualiza configurações gerais (in-memory para MVP)",
)
async def patch_config(
    patch: ConfigPatch = Body(...),
    principal: Principal = Depends(require_perm("edit_settings")),
) -> APIResponse[ConfigOut]:
    before = (await get_config()).data.model_dump()
    updates = patch.model_dump(exclude_none=True)
    if "initial_capital" in updates:
        _runtime_overrides["INITIAL_CAPITAL"] = updates["initial_capital"]
    if "orchestrator_interval_seconds" in updates:
        _runtime_overrides["ORCHESTRATOR_INTERVAL_SECONDS"] = updates["orchestrator_interval_seconds"]
    result = await get_config()
    _log_config_change(principal.actor, "system", before, result.data.model_dump())
    return result


@router.patch(
    "/agents/{agent_id}/config",
    response_model=APIResponse[AgentConfigOut],
    summary="Atualiza parâmetros de um agente",
)
async def patch_agent_config(
    agent_id: str,
    params: Dict[str, Any] = Body(...),
    registry: AgentRegistry = Depends(get_agent_registry),
    principal: Principal = Depends(require_perm("edit_settings")),
) -> APIResponse[AgentConfigOut]:
    from src.agents.registry import AGENT_REGISTRY, AGENT_PARAMS
    if agent_id not in AGENT_REGISTRY:
        raise HTTPException(status_code=404, detail={"error": "agent_not_found", "message": f"Agente '{agent_id}' não encontrado"})
    before = {k: AGENT_PARAMS.get(agent_id, {}).get(k) for k in params}
    if agent_id in AGENT_PARAMS:
        AGENT_PARAMS[agent_id].update(params)
    after = {k: AGENT_PARAMS.get(agent_id, {}).get(k) for k in params}
    _log_config_change(principal.actor, f"agent:{agent_id}", before, after)
    agent = AGENT_REGISTRY[agent_id]
    updated_params = AGENT_PARAMS.get(agent_id, {})
    return APIResponse(data=AgentConfigOut(
        id=agent.id,
        domain=agent.domain,
        implemented=agent.implemented,
        description=agent.description,
        status="active" if agent.implemented else "stub",
        cycles=0,
        params=updated_params,
    ))


_behavioral_thresholds: Dict[str, float] = {
    "revenge_size_multiplier": 1.50,
    "euphoria_size_multiplier": 1.20,
    "overconfidence_margin": 0.15,
    "risk_of_ruin_alert_pct": 5.0,
}


@router.patch(
    "/alerts/config",
    response_model=APIResponse[Dict[str, float]],
    summary="Atualiza thresholds do behavioral guard",
)
async def patch_alerts_config(
    patch: AlertsConfigPatch = Body(...),
    principal: Principal = Depends(require_perm("edit_settings")),
) -> APIResponse[Dict[str, float]]:
    updates = patch.model_dump(exclude_none=True)
    before = {k: _behavioral_thresholds.get(k) for k in updates}
    _behavioral_thresholds.update(updates)
    after = {k: _behavioral_thresholds.get(k) for k in updates}
    _log_config_change(principal.actor, "alerts", before, after)
    return APIResponse(data=dict(_behavioral_thresholds))
