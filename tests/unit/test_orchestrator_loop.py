"""Phase 4b-iii — continuous orchestrator loop contracts."""
from __future__ import annotations

import pytest

from src.agents.registry import AgentRegistry
from src.core.ledger import TradingLedger
from src.orchestration.orchestrator_loop import (
    AgentExecutionError,
    OrchestratorLoop,
    validated_interval,
)


@pytest.fixture
def ledger(tmp_path) -> TradingLedger:
    return TradingLedger(tmp_path / "trades.jsonl")


class _StubOrch:
    """Stub orchestrator: returns a result, or raises ``exc`` if provided."""

    def __init__(self, result=None, exc=None):
        self.result = result if result is not None else {"success": True, "order_id": "PAPER_1"}
        self.exc = exc
        self.calls = 0

    async def analyze_and_trade(self, symbol, timeframe="1h"):
        self.calls += 1
        if self.exc:
            raise self.exc
        return self.result


def _activities(ledger: TradingLedger):
    return [e["data"]["activity"] for e in ledger.get_events("process_event")]


# --------------------------------------------------------------- interval validation
def test_interval_validation_below_min_raises(ledger, monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_INTERVAL_SECONDS", "5")
    with pytest.raises(ValueError, match="ORCHESTRATOR_INTERVAL_SECONDS"):
        OrchestratorLoop(_StubOrch(), AgentRegistry(), ledger)


def test_interval_validation_above_max_raises():
    with pytest.raises(ValueError):
        validated_interval(3601)


def test_interval_default_is_60(ledger, monkeypatch):
    monkeypatch.delenv("ORCHESTRATOR_INTERVAL_SECONDS", raising=False)
    loop = OrchestratorLoop(_StubOrch(), AgentRegistry(), ledger)
    assert loop.interval == 60


# --------------------------------------------------------------- XES events
@pytest.mark.asyncio
async def test_loop_emits_xes_events(ledger):
    loop = OrchestratorLoop(_StubOrch(), AgentRegistry(), ledger, interval_seconds=60)
    await loop.run_cycle()
    acts = _activities(ledger)
    assert "agent_cycle_started" in acts
    assert "agent_cycle_completed" in acts
    completed = [
        e for e in ledger.get_events("process_event")
        if e["data"]["activity"] == "agent_cycle_completed"
    ][0]
    assert completed["data"]["attributes"]["duration_ms"] > 0


# --------------------------------------------------------------- fail-soft
@pytest.mark.asyncio
async def test_loop_survives_agent_failure(ledger):
    orch = _StubOrch(exc=AgentExecutionError("strategy", "boom"))
    loop = OrchestratorLoop(orch, AgentRegistry(), ledger, interval_seconds=60)

    result = await loop.run_cycle()  # must NOT raise

    acts = _activities(ledger)
    assert "agent_cycle_failed" in acts
    assert "agent_cycle_completed" in acts  # cycle still completes
    failed = [
        e for e in ledger.get_events("process_event")
        if e["data"]["activity"] == "agent_cycle_failed"
    ][0]
    assert failed["data"]["actor"] == "strategy"
    assert "boom" in failed["data"]["attributes"]["error"]
    assert result["failures"]

    # The loop is still usable on the next interval.
    orch.exc = None
    await loop.run_cycle()
    assert orch.calls == 2


# --------------------------------------------------------------- record_cycle wiring
@pytest.mark.asyncio
async def test_successful_cycle_records_agent_cycles(ledger):
    registry = AgentRegistry()
    loop = OrchestratorLoop(_StubOrch(), registry, ledger, interval_seconds=60)
    await loop.run_cycle()
    # strategy + risk always run; execution ran because the stub returned order_id.
    assert registry.status("strategy")["cycles"] == 1
    assert registry.status("risk")["cycles"] == 1
    assert registry.status("execution")["cycles"] == 1


@pytest.mark.asyncio
async def test_no_execution_when_no_order_id(ledger):
    registry = AgentRegistry()
    loop = OrchestratorLoop(
        _StubOrch(result={"success": False, "reason": "Low confidence signal"}),
        registry, ledger, interval_seconds=60,
    )
    await loop.run_cycle()
    assert registry.status("strategy")["cycles"] == 1
    assert registry.status("execution")["cycles"] == 0  # never executed
