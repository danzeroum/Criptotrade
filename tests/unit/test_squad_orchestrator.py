"""Targeted unit tests for squad_orchestrator covering uncovered branches."""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from src.core.alerts import Alert, AlertBus, AlertStore
from src.core.ledger import TradingLedger
from src.orchestration.squad_orchestrator import CircuitBreaker, SquadOrchestrator


# ── CircuitBreaker: cooldown-expired paths ────────────────────────────────────

def test_is_open_returns_false_after_cooldown_expires(monkeypatch):
    """Lines 45-46: is_open resets and returns False once cooldown elapses."""
    now = time.time()
    # Trip the breaker at `now`
    cb = CircuitBreaker()
    with patch("src.orchestration.squad_orchestrator.time") as mock_time:
        mock_time.time.return_value = now
        cb.record_trade_result(-4.5)          # trips on daily loss
    assert cb._tripped_at is not None

    # Advance time beyond the 24h cooldown
    past_cooldown = now + CircuitBreaker.COOLDOWN_SECONDS + 1
    with patch("src.orchestration.squad_orchestrator.time") as mock_time:
        mock_time.time.return_value = past_cooldown
        result = cb.is_open                   # hits lines 45-46
    assert result is False
    assert cb._tripped_at is None             # _reset was called


def test_reset_daily_resets_after_cooldown_expires(monkeypatch):
    """Lines 72-74: reset_daily triggers _reset when cooldown has elapsed."""
    now = time.time()
    cb = CircuitBreaker()
    with patch("src.orchestration.squad_orchestrator.time") as mock_time:
        mock_time.time.return_value = now
        cb.record_trade_result(-4.5)          # trips

    past_cooldown = now + CircuitBreaker.COOLDOWN_SECONDS + 1
    with patch("src.orchestration.squad_orchestrator.time") as mock_time:
        mock_time.time.return_value = past_cooldown
        cb.reset_daily()                      # hits lines 72-74

    assert cb._tripped_at is None
    assert cb._daily_loss_pct == 0.0


# ── CircuitBreaker: ledger logging in _trip and _reset ────────────────────────

def test_trip_with_ledger_does_not_crash(tmp_path):
    """Lines 82-86: _trip with ledger executes the try/except block without crashing.

    TradingLedger has no log_event method, so the AttributeError is caught
    silently — the circuit breaker must still trip correctly.
    """
    ledger = TradingLedger(tmp_path / "trades.jsonl")
    cb = CircuitBreaker(ledger=ledger)
    cb.record_trade_result(-5.0)              # triggers daily-loss trip

    # Circuit must be tripped despite ledger call failing
    assert cb.is_open is True


def test_reset_with_ledger_does_not_crash(tmp_path):
    """Lines 89-96: _reset with ledger executes try/except block without crashing."""
    ledger = TradingLedger(tmp_path / "trades.jsonl")
    now = time.time()
    cb = CircuitBreaker(ledger=ledger)
    with patch("src.orchestration.squad_orchestrator.time") as mock_time:
        mock_time.time.return_value = now
        cb.record_trade_result(-5.0)          # trips

    past_cooldown = now + CircuitBreaker.COOLDOWN_SECONDS + 1
    with patch("src.orchestration.squad_orchestrator.time") as mock_time:
        mock_time.time.return_value = past_cooldown
        result = cb.is_open                   # triggers _reset via cooldown

    # Reset executed without exception; breaker is now closed
    assert result is False
    assert cb._tripped_at is None


# ── SquadOrchestrator: constructor wires alert_sink when alert_store given ────

class _FakeExchange:
    async def fetch_ohlcv(self, *a, **kw):
        return []

    async def place_order(self, *a, **kw):
        return {"id": "EX_001"}


def test_squad_orchestrator_wires_alert_sink_from_store(tmp_path):
    """Lines 131-133: constructor calls make_guardrail_sink when alert_store provided."""
    store = AlertStore(tmp_path / "alerts.jsonl")
    orch = SquadOrchestrator(_FakeExchange(), alert_store=store)
    # The guardrail's alert_sink should now be set (not None)
    assert orch.risk_agent.guardrails.alert_sink is not None


# ── SquadOrchestrator: circuit breaker active → skip trade ───────────────────

@pytest.mark.asyncio
async def test_analyze_and_trade_skips_when_circuit_open():
    """Lines 174-175: skips trade cycle when circuit breaker is open."""
    orch = SquadOrchestrator(_FakeExchange())
    orch.circuit_breaker._tripped_at = time.time()  # manually trip

    result = await orch.analyze_and_trade("BTC/USDT")
    assert result["success"] is False
    assert "Circuit breaker" in result["reason"]


# ── SquadOrchestrator: risk rejection path (195-198) + _emit_alert (335-348) ─

class _LowConfidenceExchange:
    """Exchange that returns enough data for the stub path → high-confidence BUY."""
    async def fetch_ohlcv(self, *a, **kw):
        return []  # stub analysis used (no exchange data)


@pytest.mark.asyncio
async def test_analyze_and_trade_risk_rejection_triggers_alert(tmp_path):
    """Lines 195-198 + 335-348: risk rejection emits guardrail alert."""
    store = AlertStore(tmp_path / "alerts.jsonl")
    bus = AlertBus()

    orch = SquadOrchestrator(
        _FakeExchange(),
        alert_store=store,
        alert_bus=bus,
    )

    # Override the risk agent to always reject
    class _AlwaysRejectRiskAgent:
        guardrails = orch.risk_agent.guardrails  # keep same guardrails obj

        async def execute(self, task):
            return {
                "success": True,
                "approved": False,
                "validation": {
                    "passed": False,
                    "issues": ["Forced rejection for test"],
                },
            }

    orch.risk_agent = _AlwaysRejectRiskAgent()

    # Also raise confidence above 0.6 threshold so we don't bail early
    class _HighConfidenceStrategyAgent:
        async def execute(self, task):
            return {
                "success": True,
                "agent": "strategy",
                "confidence": 0.85,
                "signal": {
                    "action": "BUY",
                    "entry_price": 50_000.0,
                    "stop_loss": 48_000.0,
                    "take_profit": 55_000.0,
                    "position_size_pct": 2.0,
                    "symbol": "BTC/USDT",
                },
                "analysis": {},
            }

    orch.strategy_agent = _HighConfidenceStrategyAgent()

    result = await orch.analyze_and_trade("BTC/USDT")
    assert result["success"] is False
    assert result["reason"] == "Risk validation failed"

    # An alert should have been stored
    rows, total = store.history(severity="high")
    assert total >= 1


@pytest.mark.asyncio
async def test_emit_alert_no_op_without_sinks():
    """Lines 335-336: _emit_alert returns early when neither store nor bus configured."""
    orch = SquadOrchestrator(_FakeExchange())  # no alert_store, no alert_bus
    # Should not raise
    await orch._emit_alert("BTC/USDT", ["some issue"])


@pytest.mark.asyncio
async def test_emit_alert_empty_issues_uses_fallback():
    """Line 337: empty issues list → 'Risk validation failed' fallback detail."""
    store = AlertStore.__new__(AlertStore)
    store._path = None
    received = []

    def _mock_append(alert):
        received.append(alert)

    store.append = _mock_append
    orch = SquadOrchestrator(_FakeExchange(), alert_store=store)
    await orch._emit_alert("ETH/USDT", [])
    assert len(received) == 1
    assert "Risk validation failed" in received[0].message


# ── SquadOrchestrator: fill_callback path (222-236) ──────────────────────────

@pytest.mark.asyncio
async def test_analyze_and_trade_calls_fill_callback(tmp_path):
    """Lines 222-236: fill_callback called after successful execution."""
    filled = []

    async def _approve(order):
        return "order_ref_123"  # covers lines 150-151 (str result)

    orch = SquadOrchestrator(
        _FakeExchange(),
        approval_handler=_approve,
        fill_callback=lambda ref: filled.append(ref),
    )

    class _HighConfStrat:
        async def execute(self, task):
            return {
                "success": True,
                "agent": "strategy",
                "confidence": 0.85,
                "signal": {
                    "action": "BUY",
                    "entry_price": 50_000.0,
                    "stop_loss": 48_000.0,
                    "take_profit": 55_000.0,
                    "position_size_pct": 2.0,
                    "symbol": "BTC/USDT",
                },
                "analysis": {},
            }

    class _AlwaysApproveRisk:
        guardrails = orch.risk_agent.guardrails

        async def execute(self, task):
            return {
                "success": True,
                "approved": True,
                "validation": {"passed": True, "issues": []},
            }

    orch.strategy_agent = _HighConfStrat()
    orch.risk_agent = _AlwaysApproveRisk()

    result = await orch.analyze_and_trade("BTC/USDT")
    assert result["success"] is True
    # The approval handler returned a string ref, and fill_callback should have been called
    assert filled == ["order_ref_123"]


# ── SquadOrchestrator: _log_fill early return on zero price/size ──────────────

def test_log_fill_returns_early_on_zero_price():
    """Line 255: _log_fill returns without writing when price is 0."""
    orch = SquadOrchestrator(_FakeExchange())
    before = len(orch._open_positions)
    orch._log_fill("BTC/USDT", {"entry_price": 0.0, "position_size_pct": 2.0}, {})
    assert len(orch._open_positions) == before  # nothing added


def test_log_fill_returns_early_on_zero_size():
    """Line 255: _log_fill returns without writing when position_size_pct is 0."""
    orch = SquadOrchestrator(_FakeExchange())
    orch._log_fill("BTC/USDT", {"entry_price": 50_000.0, "position_size_pct": 0.0}, {})
    assert len(orch._open_positions) == 0


# ── _exit_price: sell / short TP path (329-331) ──────────────────────────────

def test_exit_price_short_tp_not_reached_returns_none():
    """Branch 329->331: short with TP not reached → return None."""
    pos = {"side": "sell", "stop_loss": 52_000.0, "take_profit": 45_000.0}
    # Current price is above TP (price not fallen to TP yet) and below SL (not triggered)
    result = SquadOrchestrator._exit_price(pos, 50_000.0)
    assert result is None


def test_exit_price_short_no_sl_no_tp_returns_none():
    """Sell position with no levels → return None via short branch."""
    pos = {"side": "sell", "stop_loss": None, "take_profit": None}
    assert SquadOrchestrator._exit_price(pos, 50_000.0) is None


# ── protocols.squad_orchestrator ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_protocols_squad_orchestrator_delegate_task():
    """Covers src/protocols/squad_orchestrator.py delegate_task."""
    from src.protocols.squad_orchestrator import SquadOrchestrator as ProtoSquad
    orch = ProtoSquad()
    result = await orch.delegate_task("Build a test suite")
    assert "plan" in result
    assert "implementation" in result
