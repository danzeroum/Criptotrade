"""Fix #2 — stub-data gate.

Without a trustworthy live price the loop must not evaluate stop/TP or open
orders: it skips the cycle, emits a throttled ``data_fallback`` event + an alert,
and only trades on stub data under the explicit ``ALLOW_STUB_DATA`` opt-in. The
gate sits BEFORE ``_check_open_positions`` so stops never fire against the fake
~$50k price (the mass stop-out that hit the legacy positions).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.core.db import init_db
from src.orchestration.squad_orchestrator import SquadOrchestrator


class _FakeExchange:
    def __init__(self):
        self.paper_trading = True

    async def create_order(self, symbol, order_type, side, amount, price=None, params=None):
        return {"id": "PAPER_x", "average": 100.0, "price": 100.0,
                "fee": {"cost": 0.0}, "status": "filled"}


class _FakeAlertStore:
    def __init__(self):
        self.alerts = []

    def append(self, alert):
        self.alerts.append(alert)


def _aqueue(items):
    it = iter(items)

    async def _fn(*_a, **_k):
        return next(it)
    return _fn


async def _approve(_o):
    return True


def _stub_sig(entry=50_000.0, *, conf=0.76):
    # Mirrors StrategyAgent._stub_analysis: flat $50k, ~0.76 BUY, stub_used flag.
    return {"signal": {"action": "buy", "entry_price": entry, "stop_loss": None,
                       "take_profit": None, "position_size_pct": 2.0},
            "confidence": conf, "stub_used": True}


def _real_sig(action, entry, *, conf=0.9):
    return {"signal": {"action": action, "entry_price": entry, "stop_loss": None,
                       "take_profit": None, "position_size_pct": 2.0},
            "confidence": conf}


_OK = {"approved": True, "validation": {"issues": []}}


@pytest.fixture
def orch(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("MAX_CONCURRENT_POSITIONS", "3")
    monkeypatch.delenv("ALLOW_STUB_DATA", raising=False)  # default false
    init_db()
    return SquadOrchestrator(_FakeExchange(), approval_handler=_approve,
                             initial_capital=10_000.0, alert_store=_FakeAlertStore())


# ------------------------------------------------------- the gate (default: off)
@pytest.mark.asyncio
async def test_stub_data_skips_cycle_and_emits_fallback(orch):
    orch.strategy_agent.execute = _aqueue([_stub_sig()])
    result = await orch.analyze_and_trade("BTC/USDT")
    assert result == {"success": False, "reason": "stub_data"}
    fb = orch.ledger.get_events("data_fallback")
    assert len(fb) == 1
    assert fb[0]["data"]["symbol"] == "BTC/USDT"
    assert fb[0]["data"]["reason"] == "stub_data"
    # the alert now actually reaches a sink (loop wiring is the bonus fix)
    assert [a.type for a in orch.alert_store.alerts] == ["data_fallback"]


@pytest.mark.asyncio
async def test_stub_data_does_not_evaluate_stop_tp(orch):
    # A long whose stop the fake $50k WOULD cross must stay open: the gate is
    # before _check_open_positions, so no stop fires on an untrustworthy price.
    orch._open_positions["btc"] = {
        "symbol": "BTC/USDT", "side": "buy", "entry_price": 60_000.0, "quantity": 1.0,
        "stop_loss": 55_000.0, "take_profit": None, "opened_at": "2026-01-01T00:00:00+00:00",
    }
    orch.strategy_agent.execute = _aqueue([_stub_sig(entry=50_000.0)])
    await orch.analyze_and_trade("BTC/USDT")
    assert "btc" in orch._open_positions  # stop NOT fired
    assert orch.ledger.get_events("position_closed") == []


@pytest.mark.asyncio
async def test_data_fallback_is_transition_then_throttled(orch):
    orch.strategy_agent.execute = _aqueue([_stub_sig(), _stub_sig()])
    await orch.analyze_and_trade("BTC/USDT")
    await orch.analyze_and_trade("BTC/USDT")  # same reason, within window → quiet
    fb = orch.ledger.get_events("data_fallback")
    assert len(fb) == 1 and fb[0]["data"]["count"] == 1


@pytest.mark.asyncio
async def test_data_fallback_heartbeat_after_window(orch):
    orch.strategy_agent.execute = _aqueue([_stub_sig(), _stub_sig()])
    await orch.analyze_and_trade("BTC/USDT")
    orch._last_fallback["BTC/USDT"]["last_emit"] -= orch._SKIP_THROTTLE_S + 1  # 10+ min later
    await orch.analyze_and_trade("BTC/USDT")
    fb = orch.ledger.get_events("data_fallback")
    assert len(fb) == 2
    assert fb[-1]["data"]["count"] == 2  # running count, not reset


@pytest.mark.asyncio
async def test_recovery_resets_fallback_so_next_outage_alerts(orch):
    # outage → recovered → outage: the second drop is a FRESH transition (a new
    # alert), never throttled into the first — the operator isn't left blind.
    orch.strategy_agent.execute = _aqueue([
        _stub_sig(),                        # outage → fallback #1
        _real_sig("buy", 100.0, conf=0.1),  # recovered (low-conf skip) → clears state
        _stub_sig(),                        # new outage → fallback #2
    ])
    await orch.analyze_and_trade("BTC/USDT")
    await orch.analyze_and_trade("BTC/USDT")
    assert "BTC/USDT" not in orch._last_fallback  # real data cleared the state
    await orch.analyze_and_trade("BTC/USDT")
    fb = orch.ledger.get_events("data_fallback")
    assert len(fb) == 2 and fb[-1]["data"]["count"] == 1  # two transitions, fresh count


# ------------------------------------------------------------ explicit opt-in
@pytest.mark.asyncio
async def test_allow_stub_data_lets_the_cycle_run(orch, monkeypatch):
    monkeypatch.setenv("ALLOW_STUB_DATA", "true")
    orch._open_positions["btc"] = {
        "symbol": "BTC/USDT", "side": "buy", "entry_price": 60_000.0, "quantity": 1.0,
        "stop_loss": 55_000.0, "take_profit": None, "opened_at": "2026-01-01T00:00:00+00:00",
    }
    orch.strategy_agent.execute = _aqueue([_stub_sig()])
    orch.risk_agent.execute = _aqueue([_OK])
    result = await orch.analyze_and_trade("BTC/USDT")
    assert result.get("reason") != "stub_data"  # not gated
    assert orch.ledger.get_events("position_closed")  # position check ran (legacy path)
    assert len(orch.ledger.get_events("data_fallback")) == 1  # still surfaced


# -------------------------------------------------------------------- A4 audit
@pytest.fixture
def api_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.delenv("AUTH_MODE", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)
    init_db()
    deps.reset_singletons()
    yield deps.get_ledger()
    deps.reset_singletons()


def test_data_fallback_is_auditable(api_env):
    api_env.log_decision("data_fallback", {"symbol": "BTC/USDT", "reason": "stub_data", "count": 1})
    r = TestClient(create_app()).get("/v1/audit?action=data_fallback")
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    assert len(rows) == 1
    assert rows[0]["action"] == "data_fallback"
    assert rows[0]["entity"] == "BTC/USDT"
