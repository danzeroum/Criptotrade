"""Agent registry — the source of truth for /v1/agents.

Honest by design (addresses Nielsen heuristic #1, system visibility):
* ``implemented`` is ``False`` for the agents that are still thin stubs
  (``recovery``, ``exploration`` are security tool-wrappers, not wired into
  trading). The API returns 501 for those instead of pretending they work.
* ``cycles_today`` is **cross-process** (Phase 5a-iii). The loop process writes a
  ``cycle_events`` row per cycle; the API reads it with an indexed
  ``SELECT COUNT`` scoped to the current UTC day — O(log n), not the O(n) JSONL
  scan that 4b-ii removed. With no ``db_path`` the registry stays fully in-memory
  (legacy behaviour, unchanged for existing tests).

There is no live ``active`` status until the loop runs; implemented agents report
``idle`` until then. This is deliberately truthful.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from src.core.db import connection, init_db


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

# Static parameter catalog — mirrors constructor defaults from each agent module.
# Values here are the authoritative source for API and dashboard display.
# Edit here when a default changes in the agent source; do not add runtime mutation.
AGENT_PARAMS: Dict[str, Dict[str, Any]] = {
    "strategy": {
        "confidence_threshold": 0.6,
        "tools": ["market_data", "technical_indicators", "pattern_recognition"],
        "active_strategies": [],
        "reasoning_pattern": "chain_of_thought",
        "autonomy_level": 2,
    },
    "risk": {
        "confidence_threshold": 0.6,
        "tools": ["portfolio_analyzer", "risk_calculator"],
        "max_position_size_pct": 5.0,
        "stop_loss_pct": 3.0,
        "max_daily_loss_pct": 5.0,
        "min_risk_reward_ratio": 2.5,
        "reasoning_pattern": "reflection",
        "autonomy_level": 3,
    },
    "execution": {
        "confidence_threshold": 0.6,
        "tools": ["place_order", "cancel_order", "get_order_status"],
        "paper_trading": True,
        "reasoning_pattern": "react",
        "autonomy_level": 1,
    },
    "supervisor": {
        "tools": [],
        "reasoning_pattern": "multi_agent",
        "autonomy_level": 2,
    },
    "architect": {
        "confidence_threshold": 0.6,
        "tools": ["analyze_architecture", "generate_adr"],
        "reasoning_pattern": "chain_of_thought",
        "autonomy_level": 2,
    },
    "auditor": {
        "confidence_threshold": 0.6,
        "tools": ["security_scan", "quality_check"],
        "complexity_threshold": 10,
        "min_coverage_pct": 80,
        "reasoning_pattern": "reflection",
        "autonomy_level": 2,
    },
    "designer": {
        "confidence_threshold": 0.6,
        "tools": ["design_mock", "accessibility_review"],
        "design_patterns": ["material", "fluent", "carbon"],
        "reasoning_pattern": "pattern_synthesis",
        "autonomy_level": 2,
    },
    "developer": {
        "confidence_threshold": 0.6,
        "tools": ["write_code", "generate_tests", "refactor", "debug", "analyze_requirements"],
        "max_iterations": 5,
        "reasoning_pattern": "react",
        "autonomy_level": 2,
    },
    "ops": {
        "confidence_threshold": 0.6,
        "tools": ["deploy_service", "configure_monitoring"],
        "deployment_strategies": ["blue-green", "canary", "rolling"],
        "reasoning_pattern": "pragmatic_planning",
        "autonomy_level": 2,
    },
    "recovery": {},
    "exploration": {},
}


def _utc_day_start() -> str:
    """ISO-8601 timestamp for 00:00:00 UTC today (lexicographically comparable)."""
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


class AgentRegistry:
    """Reports agent status; cycle counts are cross-process when ``db_path`` is set.

    Two modes, one interface:
    * ``db_path`` provided — the loop ``record_cycle`` writes ``cycle_events``;
      ``cycles_today`` reads via ``SELECT COUNT`` (cross-process truth).
    * ``db_path`` is None — fully in-memory (legacy; existing tests unchanged).

    The ``ledger`` argument is accepted for backward compatibility but ignored.
    """

    def __init__(self, ledger: Any = None, db_path: Optional[str] = None) -> None:
        if ledger is not None:
            warnings.warn(
                "AgentRegistry(ledger=...) is ignored — cycle counts are in-memory "
                "or in SQLite (see ADR-001). Drop the argument.",
                DeprecationWarning,
                stacklevel=2,
            )
        self._db_path = db_path
        if db_path is not None:
            init_db(db_path)  # idempotent: ensure cycle_events exists
        # In-memory counter: serves the loop process in O(1) and is the fallback
        # when no db_path is configured.
        self._cycles: Dict[str, int] = {}
        self._last_action: Dict[str, str] = {}
        self._cycles_date: date = datetime.now(timezone.utc).date()

    # ------------------------------------------------------------- aggregation
    def record_cycle(self, agent_id: str, when: Optional[datetime] = None) -> None:
        """Record one completed cycle for ``agent_id`` (in-memory + SQLite)."""
        when = when or datetime.now(timezone.utc)
        self._maybe_reset(when.date())
        self._cycles[agent_id] = self._cycles.get(agent_id, 0) + 1
        self._last_action[agent_id] = when.isoformat()
        if self._db_path is not None:
            with connection(self._db_path) as conn:
                conn.execute(
                    "INSERT INTO cycle_events(agent_id, cycled_at) VALUES (?, ?)",
                    (agent_id, when.isoformat()),
                )

    def cycles_today(self, agent_id: str) -> int:
        """Cycles for ``agent_id`` during the current UTC day."""
        if self._db_path is None:
            self._maybe_reset(datetime.now(timezone.utc).date())
            return self._cycles.get(agent_id, 0)
        with connection(self._db_path) as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM cycle_events WHERE agent_id=? AND cycled_at >= ?",
                (agent_id, _utc_day_start()),
            ).fetchone()[0]

    def _last_action_at(self, agent_id: str) -> Optional[str]:
        """Most recent cycle timestamp within the current UTC day, or None if no
        cycle ran today (even if there were cycles on previous days)."""
        if self._db_path is None:
            return self._last_action.get(agent_id)
        with connection(self._db_path) as conn:
            row = conn.execute(
                "SELECT MAX(cycled_at) FROM cycle_events WHERE agent_id=? AND cycled_at >= ?",
                (agent_id, _utc_day_start()),
            ).fetchone()
        return row[0] if row else None

    def _maybe_reset(self, today: date) -> None:
        """Lazy daily reset of the in-memory counters (forward-only)."""
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
        return {
            "id": info.id,
            "domain": info.domain,
            "implemented": info.implemented,
            "description": info.description,
            "status": "idle" if info.implemented else "not_implemented",
            "cycles": self.cycles_today(agent_id),
            "last_action_at": self._last_action_at(agent_id),
            "params": AGENT_PARAMS.get(agent_id, {}),
        }

    def all_statuses(self) -> List[Dict[str, Any]]:
        return [self.status(a) for a in self.list_ids()]


__all__ = ["AgentInfo", "AGENT_REGISTRY", "AGENT_PARAMS", "AgentRegistry"]

