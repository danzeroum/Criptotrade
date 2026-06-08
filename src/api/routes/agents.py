"""/v1/agents — status of the agents (honest about what is implemented).

Stubs (recovery, exploration) return 501 Not Implemented on the detail route,
so a client can tell "work in progress" apart from a real failure.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path

from src.agents.registry import AgentRegistry
from src.api.deps import get_agent_registry
from src.api.schemas import AgentConfigOut, AgentStatusOut, APIResponse

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get(
    "",
    response_model=APIResponse[List[AgentStatusOut]],
    summary="Status de todos os agentes",
)
async def list_agents(
    registry: AgentRegistry = Depends(get_agent_registry),
) -> APIResponse[List[AgentStatusOut]]:
    return APIResponse(data=[AgentStatusOut(**s) for s in registry.all_statuses()])


@router.get(
    "/{agent_id}/config",
    response_model=APIResponse[AgentConfigOut],
    summary="Configuração completa de um agente (parâmetros estáticos; funciona para stubs)",
)
async def get_agent_config(
    agent_id: str = Path(...),
    registry: AgentRegistry = Depends(get_agent_registry),
) -> APIResponse[AgentConfigOut]:
    info = registry.get(agent_id)
    if info is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "agent_not_found",
                "message": f"Agente '{agent_id}' não existe.",
                "available_agents": registry.list_ids(),
            },
        )
    return APIResponse(data=AgentConfigOut(**registry.status(agent_id)))


@router.get(
    "/{agent_id}",
    response_model=APIResponse[AgentStatusOut],
    summary="Detalhe de um agente (501 se ainda for stub)",
)
async def get_agent(
    agent_id: str = Path(...),
    registry: AgentRegistry = Depends(get_agent_registry),
) -> APIResponse[AgentStatusOut]:
    info = registry.get(agent_id)
    if info is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "agent_not_found",
                "message": f"Agente '{agent_id}' não existe.",
                "available_agents": registry.list_ids(),
            },
        )
    if not info.implemented:
        raise HTTPException(
            status_code=501,
            detail={
                "error": "not_implemented",
                "message": f"Agente '{agent_id}' está planejado mas ainda é um stub.",
                "domain": info.domain,
            },
        )
    return APIResponse(data=AgentStatusOut(**registry.status(agent_id)))
