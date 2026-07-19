"""N3 — slots, exposição e signal_skipped.

Covers the orchestrator's skip emission (state-transition + throttle, human_rejected
excluded), the slot cap (no_slot), the /v1/risk/slots and /v1/process/skips
endpoints, and that signal_skipped is auditable (A4).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.core.db import init_db
from src.orchestration.position_store import PositionStore
from src.orchestration.squad_orchestrator import SquadOrchestrator


class _FakeExchange:
    def __init__(self):
        self.paper_trading = True

    async def create_order(self, symbol, order_type, side, amount, price=None, params=None):
        return {"id": "PAPER_x", "average": 100.0, "price": 100.0,
                "fee": {"cost": 0.0}, "status": "filled"}


def _aqueue(items):
    it = iter(items)

    async def _fn(*_a, **_k):
        return next(it)
    return _fn


async def _approve(_o):
    return True


async def _reject(_o):
    return False


def _sig(action, entry, *, size=2.0, conf=0.9):
    return {"signal": {"action": action, "entry_price": entry, "stop_loss": None,
                       "take_profit": None, "position_size_pct": size}, "confidence": conf}


_OK = {"approved": True, "validation": {"issues": []}}
_LOT = {"stop_loss": None, "take_profit": None, "opened_at": "2026-01-01T00:00:00+00:00"}


@pytest.fixture
def orch(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("MAX_CONCURRENT_POSITIONS", "3")
    init_db()
    o = SquadOrchestrator(_FakeExchange(), approval_handler=_approve, initial_capital=10_000.0)
    return o


# ------------------------------------------------------ orchestrator: skip events
@pytest.mark.asyncio
async def test_confidence_low_emits_once_then_throttles(orch):
    orch.strategy_agent.execute = _aqueue([_sig("buy", 100.0, conf=0.1),
                                           _sig("buy", 100.0, conf=0.1)])
    await orch.analyze_and_trade("BTC/USDT")
    await orch.analyze_and_trade("BTC/USDT")  # same reason, within throttle → quiet
    skips = orch.ledger.get_events("signal_skipped")
    assert len(skips) == 1
    assert skips[0]["data"]["reason"] == "confidence_low"
    assert skips[0]["data"]["count"] == 1


@pytest.mark.asyncio
async def test_reason_change_emits_a_new_skip(orch):
    orch.strategy_agent.execute = _aqueue([_sig("buy", 100.0, conf=0.1),   # confidence_low
                                           _sig("buy", 100.0, conf=0.9)])  # passes → risk rejects
    orch.risk_agent.execute = _aqueue([{"approved": False,
                                        "validation": {"issues": ["Insufficient capital: ..."]}}])
    await orch.analyze_and_trade("BTC/USDT")
    await orch.analyze_and_trade("BTC/USDT")
    reasons = [e["data"]["reason"] for e in orch.ledger.get_events("signal_skipped")]
    assert reasons == ["confidence_low", "insufficient_capital"]


@pytest.mark.asyncio
async def test_no_slot_when_book_is_full(orch):
    for i in range(3):  # fill the 3 slots
        orch._open_positions[f"o{i}"] = {"symbol": f"P{i}/USDT", "side": "buy",
                                         "entry_price": 100.0, "quantity": 1.0, **_LOT}
    orch.strategy_agent.execute = _aqueue([_sig("buy", 100.0, conf=0.9)])
    orch.risk_agent.execute = _aqueue([_OK])
    result = await orch.analyze_and_trade("XRP/USDT")  # 4th, opening → no slot
    assert result["reason"] == "No free position slot"
    skips = orch.ledger.get_events("signal_skipped")
    assert skips[-1]["data"]["reason"] == "no_slot"


# -------------------------------------------- fix #1: spot semantics (no shorts)
@pytest.mark.asyncio
async def test_sell_without_inventory_skips_no_inventory(orch):
    # Spot: a SELL with no long to sell is skipped (no_inventory), never shorts.
    orch.strategy_agent.execute = _aqueue([_sig("sell", 100.0, conf=0.9)])
    orch.risk_agent.execute = _aqueue([_OK])
    result = await orch.analyze_and_trade("BTC/USDT")
    assert result["reason"] == "no_inventory"
    assert orch._open_positions == {}  # no short opened
    assert orch.ledger.get_events("signal_skipped")[-1]["data"]["reason"] == "no_inventory"


@pytest.mark.asyncio
async def test_repeated_sells_never_accumulate_shorts(orch):
    # The bug: SELLs with only same-symbol shorts open bypassed the cap and opened
    # MORE shorts, unbounded. Now every SELL without long inventory is no_inventory.
    orch.strategy_agent.execute = _aqueue([_sig("sell", 100.0, conf=0.9) for _ in range(4)])
    orch.risk_agent.execute = _aqueue([_OK for _ in range(4)])
    for _ in range(4):
        await orch.analyze_and_trade("BTC/USDT")
    assert orch._open_positions == {}  # zero shorts (was 4 before the fix)
    reasons = [e["data"]["reason"] for e in orch.ledger.get_events("signal_skipped")]
    assert reasons.count("no_inventory") == 1  # transition-only, like paused


@pytest.mark.asyncio
async def test_sell_with_long_bypasses_full_book_and_nets(orch):
    # A closing SELL frees a slot: it bypasses the cap even with the book full, and
    # nets the long (position_closed) instead of being blocked as no_slot.
    orch._open_positions["btc"] = {"symbol": "BTC/USDT", "side": "buy",
                                   "entry_price": 100.0, "quantity": 2.0, **_LOT}
    orch._open_positions["p1"] = {"symbol": "P1/USDT", "side": "buy",
                                  "entry_price": 100.0, "quantity": 1.0, **_LOT}
    orch._open_positions["p2"] = {"symbol": "P2/USDT", "side": "buy",
                                  "entry_price": 100.0, "quantity": 1.0, **_LOT}
    orch.strategy_agent.execute = _aqueue([_sig("sell", 100.0, conf=0.9)])
    orch.risk_agent.execute = _aqueue([_OK])
    result = await orch.analyze_and_trade("BTC/USDT")
    # Passed the gate (no reason == blocked); the success path returns no "reason".
    assert result.get("reason") not in ("No free position slot", "no_inventory")
    assert len(orch.ledger.get_events("position_closed")) >= 1  # the BTC long netted


@pytest.mark.asyncio
async def test_human_rejected_is_not_a_signal_skipped(orch):
    orch.approval_handler = _reject
    orch.strategy_agent.execute = _aqueue([_sig("buy", 100.0, conf=0.9)])
    orch.risk_agent.execute = _aqueue([_OK])
    await orch.analyze_and_trade("BTC/USDT")
    # Rejection is audited via hitl_approval, never duplicated as signal_skipped.
    assert orch.ledger.get_events("signal_skipped") == []
    assert len(orch.ledger.get_events("hitl_approval")) == 1


# --------------------------------------------------------------- API: slots/skips
@pytest.fixture
def api_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.delenv("AUTH_MODE", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.setenv("INITIAL_CAPITAL", "10000")
    monkeypatch.setenv("MAX_CONCURRENT_POSITIONS", "3")
    init_db()
    deps.reset_singletons()
    yield deps.get_ledger()
    deps.reset_singletons()


def test_slots_endpoint_reports_occupancy_and_exposure(api_env):
    ledger = api_env
    store = PositionStore(lambda: ledger.db_path)
    store.upsert("o1", {"symbol": "BTC/USDT", "side": "buy", "entry_price": 100.0, "quantity": 5.0, **_LOT})
    store.upsert("o2", {"symbol": "ETH/USDT", "side": "buy", "entry_price": 10.0, "quantity": 3.0, **_LOT})
    r = TestClient(create_app()).get("/v1/risk/slots")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["slots_used"] == 2 and d["slots_max"] == 3
    assert d["capital"] == 10000.0
    assert d["capital_free"] == 10000.0 - (500.0 + 30.0)
    btc = next(e for e in d["exposure"] if e["symbol"] == "BTC/USDT")
    assert btc["notional"] == 500.0 and btc["pct_of_capital"] == 5.0


def test_skips_endpoint_returns_newest_first(api_env):
    ledger = api_env
    ledger.log_decision("signal_skipped", {"symbol": "BTC/USDT", "reason": "confidence_low", "count": 1})
    ledger.log_decision("signal_skipped", {"symbol": "XRP/USDT", "reason": "no_slot", "count": 2})
    r = TestClient(create_app()).get("/v1/process/skips")
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    assert rows[0]["symbol"] == "XRP/USDT" and rows[0]["reason"] == "no_slot"  # newest first
    # filter by pair
    r2 = TestClient(create_app()).get("/v1/process/skips?symbol=BTC/USDT")
    assert [x["symbol"] for x in r2.json()["data"]] == ["BTC/USDT"]


def test_signal_skipped_is_auditable(api_env):
    ledger = api_env
    ledger.log_decision("signal_skipped", {"symbol": "BTC/USDT", "reason": "no_slot", "count": 1})
    r = TestClient(create_app()).get("/v1/audit?action=signal_skipped")
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    assert len(rows) == 1
    assert rows[0]["action"] == "signal_skipped"
    assert rows[0]["entity"] == "BTC/USDT"
