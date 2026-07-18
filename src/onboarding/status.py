"""A10 onboarding status: honest auto-detection over the real system state.

Design rule (approved plan): steps are DERIVED from real signals on every
read — a checklist that lies ("done" without a connection) is worse than none.
Only human decisions persist (skip / manual complete / dismiss / the one-time
completion stamp). Revoking the active connection flips step 1 back to
pending, exactly as it should.

Signals per step:
1. connect_exchange — active connection with a passing test (A5).
2. risk_capital    — a ``config_changed`` ledger event with scope ``risk``,
   or scope ``system`` whose diff touches ``initial_capital`` (nota 2 da
   revisão: an orchestrator-interval tweak must NOT mark this step).
3. strategy_agents — ``config_changed`` scope ``agent:*`` or an autonomy
   change (``hitl_level_changed``).
4. review          — human by principle. Brownfield exception: when steps
   1/2/3/5 are all auto-detected the system is evidently in operation and has
   been reviewed de facto — the step self-completes so a months-old VPS never
   sees the wizard on upgrade (nota 1 da revisão).
5. start_dryrun    — the ledger shows cycle activity (signal_generated /
   process_event / order_executed): the system RAN, not "someone clicked".
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.core.db import connection, get_db_path
from src.core.ledger import TradingLedger

STEP_IDS: Tuple[str, ...] = (
    "connect_exchange", "risk_capital", "strategy_agents", "review", "start_dryrun",
)

_ACTIVITY_TYPES = ("signal_generated", "process_event", "order_executed")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OnboardingStore:
    """The single persisted row: human decisions only."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db = db_path

    def _path(self):
        return self._db or get_db_path()

    def load(self) -> Dict[str, Any]:
        with connection(self._path()) as conn:
            r = conn.execute("SELECT * FROM onboarding_status WHERE id = 1").fetchone()
        if r is None:
            return {"skipped": [], "completed_manual": [], "dismissed": False,
                    "completed_at": None}
        return {
            "skipped": json.loads(r["skipped"] or "[]"),
            "completed_manual": json.loads(r["completed_manual"] or "[]"),
            "dismissed": bool(r["dismissed"]),
            "completed_at": r["completed_at"],
        }

    def save(self, state: Dict[str, Any]) -> None:
        with connection(self._path()) as conn:
            conn.execute(
                "INSERT INTO onboarding_status (id, skipped, completed_manual,"
                " dismissed, completed_at) VALUES (1, ?, ?, ?, ?)"
                " ON CONFLICT(id) DO UPDATE SET skipped = excluded.skipped,"
                " completed_manual = excluded.completed_manual,"
                " dismissed = excluded.dismissed, completed_at = excluded.completed_at",
                (json.dumps(state["skipped"]), json.dumps(state["completed_manual"]),
                 1 if state["dismissed"] else 0, state["completed_at"]),
            )


# ------------------------------------------------------------- signal probes
def _has_event(ledger: TradingLedger, types: Tuple[str, ...]) -> bool:
    marks = ",".join("?" * len(types))
    with connection(ledger.db_path) as conn:
        return conn.execute(
            f"SELECT 1 FROM ledger_events WHERE event_type IN ({marks}) LIMIT 1",
            types,
        ).fetchone() is not None


def _config_changes(ledger: TradingLedger) -> List[Dict[str, Any]]:
    # config_changed events are rare (human/config actions) — full read is fine.
    return ledger.get_events("config_changed")


def _detect_risk_capital(changes: List[Dict[str, Any]]) -> bool:
    for e in changes:
        data = e.get("data", {})
        scope = data.get("scope")
        if scope == "risk":
            return True
        if scope == "system":
            # Nota 2: only a capital change counts — an orchestrator-interval
            # tweak is unrelated to "Risco & capital".
            touched = set(data.get("before") or {}) | set(data.get("after") or {})
            if "initial_capital" in touched:
                return True
    return False


def _detect_strategy_agents(ledger: TradingLedger,
                            changes: List[Dict[str, Any]]) -> bool:
    if any(str((e.get("data") or {}).get("scope", "")).startswith("agent:")
           for e in changes):
        return True
    return _has_event(ledger, ("hitl_level_changed",))


# ----------------------------------------------------------------- computation
def compute_status(ledger: TradingLedger, connection_store,
                   store: Optional[OnboardingStore] = None) -> Dict[str, Any]:
    """Full status: derived signals merged with the persisted human decisions.
    Stamps ``completed_at`` (once) when everything is done/skipped — including
    the brownfield first GET on an already-running system."""
    store = store or OnboardingStore()
    state = store.load()
    changes = _config_changes(ledger)

    active = None
    try:
        active = connection_store.get_active()
    except Exception:  # pragma: no cover - pre-migration db
        active = None

    auto: Dict[str, Tuple[bool, str]] = {}
    if active is not None and active.get("last_test_ok"):
        auto["connect_exchange"] = (True, "{} · {} · {} · teste ok".format(
            active["label"], active["exchange_id"],
            "testnet" if active["testnet"] else "real"))
    else:
        auto["connect_exchange"] = (False, "")
    auto["risk_capital"] = (_detect_risk_capital(changes),
                            "config de risco/capital alterada")
    auto["strategy_agents"] = (_detect_strategy_agents(ledger, changes),
                               "agentes/autonomia configurados")
    auto["start_dryrun"] = (_has_event(ledger, _ACTIVITY_TYPES),
                            "ciclos detectados no ledger")

    def _status_of(step: str) -> Tuple[str, str]:
        detected, detail = auto.get(step, (False, ""))
        if detected:
            return "done_auto", detail
        if step in state["completed_manual"]:
            return "done_manual", "marcado por você"
        if step in state["skipped"]:
            return "skipped", "pulado"
        return "pending", ""

    statuses = {step: _status_of(step) for step in STEP_IDS if step != "review"}
    # Review (see module docstring): human by principle; auto only when the
    # other four steps were all auto-detected (system evidently in operation).
    others_auto = all(statuses[s][0] == "done_auto"
                      for s in ("connect_exchange", "risk_capital",
                                "strategy_agents", "start_dryrun"))
    if others_auto:
        statuses["review"] = ("done_auto", "sistema já em operação")
    elif "review" in state["completed_manual"]:
        statuses["review"] = ("done_manual", "revisado por você")
    elif "review" in state["skipped"]:
        statuses["review"] = ("skipped", "pulado")
    else:
        statuses["review"] = ("pending", "")

    steps = [{"id": step, "status": statuses[step][0], "detail": statuses[step][1]}
             for step in STEP_IDS]
    completed = all(s["status"] in ("done_auto", "done_manual", "skipped")
                    for s in steps)

    if completed and state["completed_at"] is None:
        # Stamp once — never unset (aceite: nunca reaparece, nem após restart).
        state["completed_at"] = _now()
        store.save(state)
        ledger.log_decision("onboarding_completed", {
            "actor": "system",
            "steps": {s["id"]: s["status"] for s in steps},
        })

    return {
        "steps": steps,
        "completed": completed or state["completed_at"] is not None,
        "dismissed": state["dismissed"],
        "completed_at": state["completed_at"],
    }


__all__ = ["OnboardingStore", "compute_status", "STEP_IDS"]
