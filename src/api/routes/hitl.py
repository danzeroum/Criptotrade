"""/v1/hitl/config — read and change the autonomy level (0-3).

Levels mirror the backend's level *count*; semantics are the operator-facing USD
auto-approval thresholds (see :mod:`src.hitl.config`).
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from src.api.deps import get_hitl_store
from src.api.schemas import APIResponse, AutonomyLevelPatch, HITLConfigOut
from src.hitl.config import HITLConfigStore

router = APIRouter(prefix="/hitl", tags=["hitl"])


@router.get(
    "/config",
    response_model=APIResponse[HITLConfigOut],
    summary="Configuração atual de autonomia (HITL)",
)
async def get_hitl_config(
    store: HITLConfigStore = Depends(get_hitl_store),
) -> APIResponse[HITLConfigOut]:
    return APIResponse(data=HITLConfigOut(**store.snapshot()))


@router.patch(
    "/config",
    response_model=APIResponse[HITLConfigOut],
    summary="Altera o nível de autonomia (0-3)",
)
async def update_hitl_config(
    patch: AutonomyLevelPatch = Body(...),
    store: HITLConfigStore = Depends(get_hitl_store),
) -> APIResponse[HITLConfigOut]:
    store.set_level(patch.level, patch.reason, operator=patch.operator)
    return APIResponse(data=HITLConfigOut(**store.snapshot()))
