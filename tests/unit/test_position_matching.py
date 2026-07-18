"""FIFO fill matching: an opposite-side fill closes open inventory (grid).

Covers the handoff spec E1-E5 (docs/design/design_handoff_criptotrade):
full close, short cover, partial close, over-close residue, FIFO ordering.
E6-E7 (metrics + circuit breaker) live in tests/integration/test_trading_flow.py.
"""
from __future__ import annotations

from src.core.ledger import TradingLedger
from src.orchestration.squad_orchestrator import SquadOrchestrator


class _DummyExchange:
    async def create_order(self, symbol, order_type, side, amount, price=None, params=None):
        import uuid

        return {"id": "PAPER_" + uuid.uuid4().hex[:8], "status": "filled"}


async def _approve(order):
    return True


def _make_orch(tmp_path):
    ledger = TradingLedger(tmp_path / "trades.jsonl")
    orch = SquadOrchestrator(_DummyExchange(), approval_handler=_approve)
    orch.ledger = ledger
    return orch, ledger


def _signal(action, price, size_pct=5.0, symbol="BTC/USDT"):
    return {
        "action": action, "symbol": symbol,
        "entry_price": price, "position_size_pct": size_pct,
    }


# --------------------------------------------------------------- E1: full close
def test_sell_fill_closes_open_buy_emits_pnl(tmp_path):
    orch, ledger = _make_orch(tmp_path)
    # Same signal entry price on both fills -> identical quantity (0.01 BTC).
    orch._log_fill("BTC/USDT", _signal("BUY", 50_000.0),
                   {"order_id": "PAPER_b1", "executed_price": 50_000.0, "fee": 0.5})
    orch._log_fill("BTC/USDT", _signal("SELL", 50_000.0),
                   {"order_id": "PAPER_s1", "executed_price": 51_000.0, "fee": 0.5})

    closed = ledger.get_events("position_closed")
    assert len(closed) == 1
    d = closed[0]["data"]
    assert d["order_id"] == "PAPER_b1"          # the opened lot's id
    assert d["side"] == "buy"                    # opening side (long)
    assert d["entry_price"] == 50_000.0
    assert d["exit_price"] == 51_000.0
    assert d["quantity"] == 0.01
    # gross (51000-50000)*0.01 = 10, net of both fees (0.5 entry + 0.5 exit).
    assert d["pnl"] == 9.0

    assert orch._open_positions == {}
    assert orch._positions.count() == 0


# --------------------------------------------------------------- E2: short cover
def test_buy_fill_closes_open_short(tmp_path):
    orch, ledger = _make_orch(tmp_path)
    orch._log_fill("BTC/USDT", _signal("SELL", 50_000.0),
                   {"order_id": "PAPER_s1", "executed_price": 50_000.0})
    orch._log_fill("BTC/USDT", _signal("BUY", 50_000.0),
                   {"order_id": "PAPER_b1", "executed_price": 49_000.0})

    closed = ledger.get_events("position_closed")
    assert len(closed) == 1
    d = closed[0]["data"]
    assert d["side"] == "sell"                   # opening side (short)
    # direction -1: (49000-50000)*0.01*-1 = +10 (covered lower -> profit).
    assert d["pnl"] == 10.0
    assert orch._open_positions == {}
    assert orch._positions.count() == 0


# ------------------------------------------------------------ E3: partial close
def test_partial_close_reduces_lot(tmp_path):
    orch, _ledger = _make_orch(tmp_path)
    orch._match_or_open(symbol="BTC/USDT", side="buy", price=100.0,
                        quantity=1.0, fee=0.0, order_id="b1")
    orch._match_or_open(symbol="BTC/USDT", side="sell", price=110.0,
                        quantity=0.4, fee=0.0, order_id="s1")

    closed = orch.ledger.get_events("position_closed")
    assert len(closed) == 1
    d = closed[0]["data"]
    assert d["order_id"] == "b1"
    assert d["quantity"] == 0.4
    assert d["pnl"] == 4.0                       # (110-100)*0.4

    # Remaining lot shrinks in place, in memory and in the operational store.
    assert orch._open_positions["b1"]["quantity"] == 0.6
    stored = orch._positions.load_all()
    assert stored["b1"]["quantity"] == 0.6
    assert orch._positions.count() == 1


# ------------------------------------------------- E4: over-close nets residual
def test_over_close_nets_to_residual_short(tmp_path):
    orch, _ledger = _make_orch(tmp_path)
    orch._match_or_open(symbol="BTC/USDT", side="buy", price=100.0,
                        quantity=0.4, fee=0.0, order_id="b1")
    orch._match_or_open(symbol="BTC/USDT", side="sell", price=110.0,
                        quantity=1.0, fee=0.0, order_id="s1")

    closed = orch.ledger.get_events("position_closed")
    assert len(closed) == 1
    assert closed[0]["data"]["quantity"] == 0.4  # the buy lot, fully closed

    # Residue opens a short under the sell's order id.
    assert set(orch._open_positions) == {"s1"}
    residual = orch._open_positions["s1"]
    assert residual["side"] == "sell"
    assert residual["entry_price"] == 110.0
    assert abs(residual["quantity"] - 0.6) < 1e-12
    stored = orch._positions.load_all()
    assert abs(stored["s1"]["quantity"] - 0.6) < 1e-12


# ----------------------------------------------------------- E5: FIFO ordering
def test_fifo_closes_oldest_first(tmp_path):
    orch, _ledger = _make_orch(tmp_path)
    for i, (oid, opened_at) in enumerate([
        ("b1", "2026-01-01T00:00:00+00:00"),
        ("b2", "2026-01-02T00:00:00+00:00"),
        ("b3", "2026-01-03T00:00:00+00:00"),
    ]):
        orch._open_positions[oid] = {
            "symbol": "BTC/USDT", "side": "buy", "entry_price": 100.0 + i,
            "quantity": 0.5, "stop_loss": None, "take_profit": None,
            "opened_at": opened_at,
        }
        orch._positions.upsert(oid, orch._open_positions[oid])

    orch._match_or_open(symbol="BTC/USDT", side="sell", price=120.0,
                        quantity=0.5, fee=0.0, order_id="s1")

    closed = orch.ledger.get_events("position_closed")
    assert len(closed) == 1
    assert closed[0]["data"]["order_id"] == "b1"  # oldest lot goes first
    assert set(orch._open_positions) == {"b2", "b3"}
    assert orch._positions.count() == 2
