"""Agent registry — the source of truth for /v1/agents.

Honest by design (addresses Nielsen heuristic #1, system visibility):
* ``implemented`` is ``False`` for the agents that are still thin stubs
  (``recovery``, ``exploration`` are security tool-wrappers, not wired into
  trading). The API returns 501 for those instead of pretending they work.
* For the trading agents, ``cycles`` and ``last_action_at`` are derived from
  *real* ledger events, not fabricated.

There is no continuous agent loop yet, so a live ``active`` status is not
claimed: implemented agents report ``idle`` until the orchestrator runs
continuously (Phase 4). This is deliberately truthful.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.core.ledger import TradingLedger


@dataclass(frozen=True)
class AgentInfo:
    id: str
    domain: str  # trading | engineering | orchestration | security
    implemented: bool
    description: str


# Curated from the actual modules in src/agents/. The trading trio drives
# SquadOrchestrator; the engineering squad drives UnifiedOrchestrator; the two
# security agents are stubs awaiting real tooling.
AGENT_REGISTRY: Dict[str, AgentInfo] = {
    a.id: a
    for a in [
        AgentInfo("strategy", "trading", True, "Gera sinais de trading (CoT)."),
        AgentInfo("risk", "trading", True, "Valida ordens contra guardrails (reflexão)."),
        AgentInfo("execution", "trading", True, "Executa ordens aprovadas (paper)."),
        AgentInfo("supervisor", "orchestration", True, "Coordena agentes especialistas."),
        AgentInfo("architect", "engineering", True, "Análise de arquitetura (CoT)."),
        AgentInfo("auditor", "engineering", True, "Auditoria de segurança/qualidade."),
        AgentInfo("designer", "engineering", True, "Artefatos de design/UX."),
        AgentInfo("developer", "engineering", True, "Implementação (ReAct)."),
        AgentInfo("ops", "engineering", True, "Runbooks de deploy/monitoramento."),
        AgentInfo("recovery", "security", False, "Stub: remediação pós-incidente."),
        AgentInfo("exploration", "security", False, "Stub: varredura de vulnerabilidades."),
    ]
}

# Maps trading ledger event types to the agent that produces them, so we can
# count real cycles per agent from the audit trail.
_LEDGER_ACTIVITY_BY_AGENT = {
    "strategy": "signal_generated",
    "risk": "risk_validation",
    "execution": "order_executed",
}


class AgentRegistry:
    """Reports agent status, enriched with real counters from the ledger."""

    def __init__(self, ledger: TradingLedger) -> None:
        self._ledger = ledger

    def list_ids(self) -> List[str]:
        return list(AGENT_REGISTRY.keys())

    def get(self, agent_id: str) -> Optional[AgentInfo]:
        return AGENT_REGISTRY.get(agent_id)

    def status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        info = AGENT_REGISTRY.get(agent_id)
        if info is None:
            return None
        cycles, last_action = self._ledger_stats(agent_id)
        return {
            "id": info.id,
            "domain": info.domain,
            "implemented": info.implemented,
            "description": info.description,
            "status": "idle" if info.implemented else "not_implemented",
            "cycles": cycles,
            "last_action_at": last_action,
        }

    def all_statuses(self) -> List[Dict[str, Any]]:
        return [self.status(a) for a in self.list_ids()]

    def _ledger_stats(self, agent_id: str) -> tuple[int, Optional[str]]:
        """Real cycle count + last action time from the trading ledger."""
        activity = _LEDGER_ACTIVITY_BY_AGENT.get(agent_id)
        if activity is None:
            return 0, None
        events = self._ledger.get_events(activity)
        if not events:
            return 0, None
        return len(events), events[-1].get("timestamp")


__all__ = ["AgentInfo", "AGENT_REGISTRY", "AgentRegistry"]
