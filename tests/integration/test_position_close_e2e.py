"""End-to-end proof that the DEPLOYED close pipeline actually fires.

The unit tests (tests/unit/test_position_matching.py) prove ``_match_or_open``
/``_record_close`` in isolation. This test closes the remaining gap the VPS
soak raised: does the FULL production path — ``analyze_and_trade`` → HITL
approval → ``ExecutionAgent`` (paper order) → ``_log_fill`` → matching /
stop-TP → ledger — actually emit ``position_closed``?

Only the two AI *decisions* are stubbed (strategy signal + risk approval —
neither is close logic). Everything that books a close runs for real:
HITL, the real ``ExecutionAgent``, ``_log_fill``, ``_match_or_open``,
``_check_open_positions``, ``_record_close``, the ledger and the circuit
breaker. A fake exchange returns a controlled fill price so the P&L is
deterministic — the same seam the real paper exchange fills through
(``create_order`` → ``{id, average, fee, status}``).
"""
from __future__ import annotations

import pytest

from src.core.db import init_db
from src.orchestration.squad_orchestrator import SquadOrchestrator


class _FakeExchange:
    """Minimal stand-in for ExchangeClient's paper ``create_order`` seam:
    returns a UNIQUE order id and a controllable executed price/fee."""

    def __init__(self) -> None:
        self.paper_trading = True
        self.next_price = 100.0
        self.next_fee = 0.0
        self._n = 0

    async def create_order(self, symbol, order_type, side, amount,
                           price=None, params=None):
        self._n += 1
        return {
            "id": f"PAPER_e2e_{self._n}",   # unique, like PAPER_<uuid>
            "average": self.next_price,
            "price": self.next_price,
            "fee": {"cost": self.next_fee},
            "status": "filled",
        }


def _aqueue(items):
    """Async callable that returns queued results in order (agent stub)."""
    it = iter(items)

    async def _fn(*_a, **_k):
        return next(it)

    return _fn


async def _approve(_order):
    return True


@pytest.fixture
def orch(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("MAX_POSITION_SIZE_PCT", "10")  # keep sizing permissive
    init_db()
    fake = _FakeExchange()
    o = SquadOrchestrator(exchange_client=fake, approval_handler=_approve,
                          initial_capital=10_000.0)
    o._fake = fake  # test handle for the controlled price
    return o


def _signal(action, entry, *, sl=None, tp=None, size=2.0, conf=0.9):
    return {
        "signal": {
            "action": action, "entry_price": entry,
            "stop_loss": sl, "take_profit": tp, "position_size_pct": size,
        },
        "confidence": conf,
    }


_APPROVED = {"approved": True, "validation": {"issues": []}}


# --------------------------------- close path 1: FIFO grid netting (a SELL)
@pytest.mark.asyncio
async def test_sell_cycle_closes_a_buy_lot_end_to_end(orch):
    orch.strategy_agent.execute = _aqueue([
        _signal("BUY", 100.0, sl=97.0, tp=300.0),   # opens; TP far so only the SELL closes
        _signal("SELL", 110.0, sl=113.0, tp=50.0),  # nets against the open buy
    ])
    orch.risk_agent.execute = _aqueue([_APPROVED, _APPROVED])

    orch._fake.next_price = 100.0
    await orch.analyze_and_trade("BTC/USDT")
    # The buy lot is booked through the REAL pipeline.
    assert len(orch._open_positions) == 1
    assert orch.ledger.get_events("position_closed") == []

    orch._fake.next_price = 110.0
    await orch.analyze_and_trade("BTC/USDT")

    closed = orch.ledger.get_events("position_closed")
    assert len(closed) == 1, "a SELL fill must close the open BUY lot"
    data = closed[0]["data"]
    assert data["symbol"] == "BTC/USDT" and data["side"] == "buy"
    assert data["entry_price"] == 100.0 and data["exit_price"] == 110.0
    assert data["pnl"] > 0  # bought at 100, sold at 110


# --------------------------------- close path 2: stop/take-profit exit
@pytest.mark.asyncio
async def test_take_profit_closes_a_position_end_to_end(orch):
    orch.strategy_agent.execute = _aqueue([
        _signal("BUY", 100.0, sl=97.0, tp=105.0),        # opens with TP at 105
        _signal("HOLD", 106.0, size=0.0, conf=0.1),      # price>TP → close-check fires
    ])
    orch.risk_agent.execute = _aqueue([_APPROVED])  # only cycle 1 reaches risk

    orch._fake.next_price = 100.0
    await orch.analyze_and_trade("BTC/USDT")
    assert len(orch._open_positions) == 1

    # Cycle 2 is low-confidence (skips a new trade) but _check_open_positions
    # still runs at the top of the cycle against current price 106 ≥ TP 105.
    await orch.analyze_and_trade("BTC/USDT")

    closed = orch.ledger.get_events("position_closed")
    assert len(closed) == 1, "take-profit must close the open lot"
    data = closed[0]["data"]
    assert data["exit_price"] == 105.0  # exited exactly at the TP
    assert data["pnl"] > 0
    assert orch._open_positions == {}  # lot removed from the book


# ---------------------------- realised P&L flows back into the metrics read
@pytest.mark.asyncio
async def test_closed_pnl_is_readable_as_realised(orch):
    orch.strategy_agent.execute = _aqueue([
        _signal("BUY", 100.0, tp=300.0),
        _signal("SELL", 120.0, tp=50.0),
    ])
    orch.risk_agent.execute = _aqueue([_APPROVED, _APPROVED])
    orch._fake.next_price = 100.0
    await orch.analyze_and_trade("BTC/USDT")
    orch._fake.next_price = 120.0
    await orch.analyze_and_trade("BTC/USDT")

    assert orch._realized_pnl() > 0
    assert len(orch.ledger.get_events("position_closed")) == 1
