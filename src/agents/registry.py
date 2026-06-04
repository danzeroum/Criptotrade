"""Agent registry — the source of truth for /v1/agents.

Honest by design (addresses Nielsen heuristic #1, system visibility):
* ``implemented`` is ``False`` for the agents that are still thin stubs
  (``recovery``, ``exploration`` are security tool-wrappers, not wired into
  trading). The API returns 501 for those instead of pretending they work.
* ``cycles_today`` is an **in-memory O(1) counter** incremented by the
  orchestrator loop via :meth:`record_cycle`, NOT a scan of the JSONL ledger on
  every request. With a continuous loop emitting ~17k events/day and a dashboard
  refreshing every 5s, scanning the file per request would be millions of line
  reads/day (see ADR-001). The counter resets lazily at the first access of a new
  UTC day, so it always reflects "today".

There is no live ``active`` status until the loop runs; implemented agents report
``idle`` until then. This is deliberately truthful.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional


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


class AgentRegistry:
    """Reports agent status with O(1) in-memory cycle counters.

    The ``ledger`` argument is accepted for wiring compatibility but is no longer
    read on the hot path: cycle counts come from memory (see module docstring).
    """

    def __init__(self, ledger: Any = None) -> None:
        # Tech debt guard: the ledger is no longer used for cycles (in-memory now).
        # Warn loudly so a caller passing it expecting it to be scanned isn't bitten
        # by a silent no-op.
        if ledger is not None:
            warnings.warn(
                "AgentRegistry(ledger=...) is ignored — cycle counts are in-memory "
                "(see ADR-001). Drop the argument.",
                DeprecationWarning,
                stacklevel=2,
            )
        self._ledger = None  # reserved; never scanned per request
        self._cycles: Dict[str, int] = {}
        self._last_action: Dict[str, str] = {}
        self._cycles_date: date = datetime.now(timezone.utc).date()

    # ------------------------------------------------------------- aggregation
    def record_cycle(self, agent_id: str, when: Optional[datetime] = None) -> None:
        """Increment an agent's cycle counter (called on ``agent_cycle_completed``)."""
        when = when or datetime.now(timezone.utc)
        self._maybe_reset(when.date())
        self._cycles[agent_id] = self._cycles.get(agent_id, 0) + 1
        self._last_action[agent_id] = when.isoformat()

    def _maybe_reset(self, today: date) -> None:
        """Lazy daily reset: a new UTC day zeroes the per-agent counters.

        Only resets moving *forward* (``>``): wall-clock time never goes back, and
        this keeps reads consistent regardless of access order.
        """
        if today > self._cycles_date:
            self._cycles.clear()
            self._last_action.clear()
            self._cycles_date = today

    # ----------------------------------------------------------------- queries
    def list_ids(self) -> List[str]:
        return list(AGENT_REGISTRY.keys())

    def get(self, agent_id: str) -> Optional[AgentInfo]:
        return AGENT_REGISTRY.get(agent_id)

    def status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        info = AGENT_REGISTRY.get(agent_id)
        if info is None:
            return None
        self._maybe_reset(datetime.now(timezone.utc).date())
        return {
            "id": info.id,
            "domain": info.domain,
            "implemented": info.implemented,
            "description": info.description,
            "status": "idle" if info.implemented else "not_implemented",
            "cycles": self._cycles.get(agent_id, 0),
            "last_action_at": self._last_action.get(agent_id),
        }

    def all_statuses(self) -> List[Dict[str, Any]]:
        return [self.status(a) for a in self.list_ids()]


__all__ = ["AgentInfo", "AGENT_REGISTRY", "AgentRegistry"]
