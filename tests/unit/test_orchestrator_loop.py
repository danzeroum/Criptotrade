"""Phase 4b-iii — continuous orchestrator loop contracts."""
from __future__ import annotations

import pytest

from src.agents.registry import AgentRegistry
from src.core.ledger import TradingLedger
from src.orchestration.orchestrator_loop import (
    AgentExecutionError,
    OrchestratorLoop,
    _symbols_from_env,
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


@pytest.mark.asyncio
async def test_cycle_logs_per_symbol_duration(ledger):
    """N6: the cycle event carries a per-symbol duration map (additive field)."""
    loop = OrchestratorLoop(_StubOrch(), AgentRegistry(), ledger,
                            symbols=["BTC/USDT", "ETH/USDT"], interval_seconds=60)
    await loop.run_cycle()
    completed = [
        e for e in ledger.get_events("process_event")
        if e["data"]["activity"] == "agent_cycle_completed"
    ][0]
    attrs = completed["data"]["attributes"]
    # Additive: the existing shape is untouched.
    assert attrs["duration_ms"] > 0 and "ran" in attrs and "failures" in attrs
    # New: a per-symbol breakdown for every symbol in the cycle.
    assert set(attrs["per_symbol"]) == {"BTC/USDT", "ETH/USDT"}
    assert all(v >= 0 for v in attrs["per_symbol"].values())


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


# --------------------------------------------------------------- real wiring (Candidate A)
@pytest.mark.asyncio
async def test_from_env_wires_real_handler_and_executes(tmp_path, monkeypatch):
    monkeypatch.setenv("EXCHANGE_DRY_RUN", "true")
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path / "ledger"))
    monkeypatch.setenv("AUTONOMY_LEVEL", "3")  # threshold $5000 -> small order auto-approves

    # Drive the pipeline with a controlled *sideways* market so the Grid strategy
    # clears the 0.60 confidence gate deterministically. The production dry-run
    # generator is intentionally realistic (trends + choppiness) and legitimately
    # HOLDs in most conditions, so this end-to-end wiring test pins both the clock
    # and a flat/ranging series rather than depending on the live generator's stats.
    import math
    import src.core.synthetic_market as synth

    def _sideways_price(base, ts, amplitude=0.02):
        return base * (1 + amplitude * math.sin(2 * math.pi * ts / 3600))

    def _sideways_ohlcv(base, ts, timeframe="1h", limit=100):
        tf = synth.timeframe_seconds(timeframe)
        rows = []
        for i in range(limit):
            bucket = ts - (limit - 1 - i) * tf
            close, open_ = _sideways_price(base, bucket), _sideways_price(base, bucket - tf)
            rows.append([bucket * 1000, open_, max(open_, close) * 1.001, min(open_, close) * 0.999, close, 1.0])
        return rows

    monkeypatch.setattr("time.time", lambda: 1_700_000_000.0)
    monkeypatch.setattr(synth, "synthetic_price", _sideways_price)
    monkeypatch.setattr(synth, "synthetic_ohlcv", _sideways_ohlcv)

    loop = OrchestratorLoop.from_env(symbols=["BTC/USDT"])
    assert loop.orchestrator.approval_handler is not None  # real handler wired

    result = await loop.run_cycle()
    # Full pipeline ran end-to-end: strategy -> risk -> HITL(auto) -> execution.
    assert "strategy" in result["ran"]
    assert "risk" in result["ran"]
    assert "execution" in result["ran"]


@pytest.mark.asyncio
async def test_from_env_level_zero_keeps_order_pending(tmp_path, monkeypatch):
    monkeypatch.setenv("EXCHANGE_DRY_RUN", "true")
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path / "ledger0"))
    monkeypatch.setenv("AUTONOMY_LEVEL", "0")  # manual: nothing auto-approves

    loop = OrchestratorLoop.from_env(symbols=["BTC/USDT"])
    loop.order_store._poll_interval = 0.02
    loop.order_store._decision_timeout = 0.05  # fail-closed fast for the test

    result = await loop.run_cycle()
    # No human approved -> order times out (cancelled), execution never runs.
    assert "execution" not in result["ran"]


# --------------------------------------------------------------- clean shutdown
@pytest.mark.asyncio
async def test_run_forever_stops_cleanly(ledger):
    import asyncio

    orch = _StubOrch()
    loop = OrchestratorLoop(orch, AgentRegistry(), ledger, interval_seconds=10)

    task = asyncio.create_task(loop.run_forever())
    await asyncio.sleep(0.05)  # let at least one cycle run
    loop.stop()  # must wake the interval wait immediately (asyncio.Event)
    await asyncio.wait_for(task, timeout=2.0)  # would time out if stop() blocked

    assert orch.calls >= 1


# ----------------------------------------------------------- multi-symbol env
def test_symbols_from_env_unset_defaults_btc(monkeypatch):
    monkeypatch.delenv("SYMBOLS", raising=False)
    assert _symbols_from_env() == ["BTC/USDT"]


def test_symbols_from_env_explicit_list(monkeypatch):
    monkeypatch.delenv("MARKET_PAIRS", raising=False)  # default allowlist
    monkeypatch.setenv("SYMBOLS", "ETH/USDT, btc/usdt")
    assert _symbols_from_env() == ["BTC/USDT", "ETH/USDT"]  # sorted, upper-cased


def test_symbols_from_env_drops_pairs_outside_allowlist(monkeypatch):
    monkeypatch.delenv("MARKET_PAIRS", raising=False)
    monkeypatch.setenv("SYMBOLS", "BTC/USDT,FOO/BAR")
    assert _symbols_from_env() == ["BTC/USDT"]  # FOO/BAR not allowed -> dropped


def test_symbols_from_env_all_invalid_defaults_btc(monkeypatch):
    monkeypatch.delenv("MARKET_PAIRS", raising=False)
    monkeypatch.setenv("SYMBOLS", "FOO/BAR")
    assert _symbols_from_env() == ["BTC/USDT"]


def test_from_env_reads_symbols_env(tmp_path, monkeypatch):
    monkeypatch.setenv("EXCHANGE_DRY_RUN", "true")
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path / "ledger_sym"))
    monkeypatch.delenv("MARKET_PAIRS", raising=False)
    monkeypatch.setenv("SYMBOLS", "BTC/USDT,ETH/USDT")
    loop = OrchestratorLoop.from_env()
    assert loop.symbols == ["BTC/USDT", "ETH/USDT"]


def test_from_env_explicit_symbols_override_env(tmp_path, monkeypatch):
    monkeypatch.setenv("EXCHANGE_DRY_RUN", "true")
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path / "ledger_sym2"))
    monkeypatch.setenv("SYMBOLS", "ETH/USDT,SOL/USDT")  # must be ignored
    loop = OrchestratorLoop.from_env(symbols=["BTC/USDT"])
    assert loop.symbols == ["BTC/USDT"]
