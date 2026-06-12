import asyncio

import pytest

from src.core.ledger import TradingLedger
from src.core.metrics import PortfolioMetricsCalculator
from src.hitl.orders import OrderStatus, OrderStore, make_approval_handler
from src.orchestration.squad_orchestrator import SquadOrchestrator


class _DummyExchange:
    pass


async def _approve(order):
    return True


@pytest.mark.asyncio
async def test_analyze_and_trade_success(tmp_path):
    orchestrator = SquadOrchestrator(_DummyExchange(), approval_handler=_approve)
    ledger_path = tmp_path / "trades.jsonl"
    orchestrator.ledger = TradingLedger(ledger_path)

    result = await orchestrator.analyze_and_trade("BTC/USDT", timeframe="1h")

    assert result["success"] is True
    assert result["order_id"].startswith("PAPER_")
    entries = orchestrator.ledger.read_all()
    assert len(entries) >= 3  # signal, validation, execution


@pytest.mark.asyncio
async def test_manual_approval_completes_to_filled(tmp_path):
    # Follow-up #1: the manual path (approved -> loop executes -> filled).
    ledger = TradingLedger(tmp_path / "trades.jsonl")
    store = OrderStore(
        ledger, threshold_provider=lambda: 0.0,  # nothing auto-approves
        db_path=str(tmp_path / "orders.db"), poll_interval=0.02,
    )
    orchestrator = SquadOrchestrator(
        _DummyExchange(),
        approval_handler=make_approval_handler(store),
        fill_callback=store.mark_filled,
    )
    orchestrator.ledger = ledger

    task = asyncio.create_task(orchestrator.analyze_and_trade("BTC/USDT"))
    await asyncio.sleep(0.05)
    pending = store.list(status=OrderStatus.pending)
    assert len(pending) == 1
    assert pending[0].pair == "BTC/USDT"  # follow-up #2: symbol injected, not UNKNOWN

    # The "API" approves on the shared store; the loop executes and marks filled.
    store.resolve(pending[0].id, approved=True, operator="daniel")
    result = await asyncio.wait_for(task, timeout=2.0)
    assert result["success"] is True
    assert store.get(pending[0].id).status == OrderStatus.filled


@pytest.mark.asyncio
async def test_analyze_and_trade_blocked_when_no_hitl_handler(tmp_path):
    # Fail-closed: with no approval handler, the trade must be rejected.
    orchestrator = SquadOrchestrator(_DummyExchange())
    orchestrator.ledger = TradingLedger(tmp_path / "trades.jsonl")

    result = await orchestrator.analyze_and_trade("BTC/USDT", timeframe="1h")

    assert result["success"] is False
    assert result["reason"] == "Human rejected the trade"


@pytest.mark.asyncio
async def test_analyze_and_trade_rejected_when_low_confidence(tmp_path, monkeypatch):
    orchestrator = SquadOrchestrator(_DummyExchange())
    orchestrator.ledger = TradingLedger(tmp_path / "trades.jsonl")

    async def low_confidence_execute(task):
        return {
            "success": True,
            "agent": "strategy",
            "signal": {"action": "BUY", "symbol": task["symbol"]},
            "confidence": 0.2,
            "analysis": {},
        }

    monkeypatch.setattr(orchestrator.strategy_agent, "execute", low_confidence_execute)

    result = await orchestrator.analyze_and_trade("ETH/USDT")

    assert result["success"] is False
    assert result["reason"] == "Low confidence signal"


# ----------------------------------------------------------------- P1-5: position close
def _make_orch(tmp_path):
    ledger = TradingLedger(tmp_path / "trades.jsonl")
    orch = SquadOrchestrator(_DummyExchange(), approval_handler=_approve)
    orch.ledger = ledger
    return orch, ledger


def test_exit_price_stop_loss_triggers():
    from src.orchestration.squad_orchestrator import SquadOrchestrator
    pos = {"side": "buy", "stop_loss": 48_000.0, "take_profit": 55_000.0}
    assert SquadOrchestrator._exit_price(pos, 47_000.0) == 48_000.0


def test_exit_price_take_profit_triggers():
    from src.orchestration.squad_orchestrator import SquadOrchestrator
    pos = {"side": "buy", "stop_loss": 48_000.0, "take_profit": 55_000.0}
    assert SquadOrchestrator._exit_price(pos, 56_000.0) == 55_000.0


def test_exit_price_in_range_returns_none():
    from src.orchestration.squad_orchestrator import SquadOrchestrator
    pos = {"side": "buy", "stop_loss": 48_000.0, "take_profit": 55_000.0}
    assert SquadOrchestrator._exit_price(pos, 51_000.0) is None


def test_check_open_positions_stop_loss(tmp_path):
    orch, ledger = _make_orch(tmp_path)
    orch._open_positions["ord_1"] = {
        "symbol": "BTC/USDT", "side": "buy",
        "entry_price": 50_000.0, "quantity": 0.1,
        "stop_loss": 48_000.0, "take_profit": 55_000.0,
        "opened_at": "2026-01-01T00:00:00+00:00",
    }
    ledger.log_fill("ord_1", "BTC/USDT", "buy", 50_000.0, 0.1)

    orch._check_open_positions(47_000.0, "BTC/USDT")

    assert len(orch._open_positions) == 0
    closed = ledger.get_events("position_closed")
    assert len(closed) == 1
    d = closed[0]["data"]
    assert d["order_id"] == "ord_1"
    assert d["exit_price"] == 48_000.0
    assert d["pnl"] < 0


def test_check_open_positions_take_profit(tmp_path):
    orch, ledger = _make_orch(tmp_path)
    orch._open_positions["ord_2"] = {
        "symbol": "BTC/USDT", "side": "buy",
        "entry_price": 50_000.0, "quantity": 0.1,
        "stop_loss": 48_000.0, "take_profit": 55_000.0,
        "opened_at": "2026-01-01T00:00:00+00:00",
    }
    ledger.log_fill("ord_2", "BTC/USDT", "buy", 50_000.0, 0.1)

    orch._check_open_positions(56_000.0, "BTC/USDT")

    closed = ledger.get_events("position_closed")
    assert len(closed) == 1
    assert closed[0]["data"]["exit_price"] == 55_000.0
    assert closed[0]["data"]["pnl"] > 0


# --- short (sell) positions: the else-branch of _exit_price + the pnl direction ---

def test_exit_price_short_stop_loss_triggers():
    from src.orchestration.squad_orchestrator import SquadOrchestrator
    pos = {"side": "sell", "stop_loss": 52_000.0, "take_profit": 45_000.0}
    # a short's stop sits above entry: triggered when price rises through it
    assert SquadOrchestrator._exit_price(pos, 53_000.0) == 52_000.0


def test_exit_price_short_take_profit_triggers():
    from src.orchestration.squad_orchestrator import SquadOrchestrator
    pos = {"side": "sell", "stop_loss": 52_000.0, "take_profit": 45_000.0}
    # a short's target sits below entry: triggered when price falls through it
    assert SquadOrchestrator._exit_price(pos, 44_000.0) == 45_000.0


def test_check_open_positions_short_stop_loss(tmp_path):
    orch, ledger = _make_orch(tmp_path)
    orch._open_positions["ord_s1"] = {
        "symbol": "BTC/USDT", "side": "sell",
        "entry_price": 50_000.0, "quantity": 0.1,
        "stop_loss": 52_000.0, "take_profit": 45_000.0,
        "opened_at": "2026-01-01T00:00:00+00:00",
    }
    ledger.log_fill("ord_s1", "BTC/USDT", "sell", 50_000.0, 0.1)

    orch._check_open_positions(53_000.0, "BTC/USDT")

    assert len(orch._open_positions) == 0
    closed = ledger.get_events("position_closed")
    assert len(closed) == 1
    assert closed[0]["data"]["exit_price"] == 52_000.0
    assert closed[0]["data"]["pnl"] < 0  # short stopped out above entry => loss


def test_check_open_positions_short_take_profit(tmp_path):
    orch, ledger = _make_orch(tmp_path)
    orch._open_positions["ord_s2"] = {
        "symbol": "BTC/USDT", "side": "sell",
        "entry_price": 50_000.0, "quantity": 0.1,
        "stop_loss": 52_000.0, "take_profit": 45_000.0,
        "opened_at": "2026-01-01T00:00:00+00:00",
    }
    ledger.log_fill("ord_s2", "BTC/USDT", "sell", 50_000.0, 0.1)

    orch._check_open_positions(44_000.0, "BTC/USDT")

    closed = ledger.get_events("position_closed")
    assert len(closed) == 1
    assert closed[0]["data"]["exit_price"] == 45_000.0
    assert closed[0]["data"]["pnl"] > 0  # short hit target below entry => profit


def test_check_open_positions_only_affects_matching_symbol(tmp_path):
    orch, ledger = _make_orch(tmp_path)
    orch._open_positions["ord_3"] = {
        "symbol": "ETH/USDT", "side": "buy",
        "entry_price": 3_000.0, "quantity": 1.0,
        "stop_loss": 2_800.0, "take_profit": None,
        "opened_at": "2026-01-01T00:00:00+00:00",
    }
    orch._check_open_positions(1.0, "BTC/USDT")  # different symbol
    assert len(orch._open_positions) == 1  # ETH position untouched


@pytest.mark.asyncio
async def test_full_cycle_fill_tracked_then_closed(tmp_path):
    orch, ledger = _make_orch(tmp_path)

    result = await orch.analyze_and_trade("BTC/USDT")
    assert result["success"] is True
    assert len(orch._open_positions) == 1
    assert len(ledger.get_events("position_closed")) == 0

    # Price below any stop level for stub (entry ≈ 50k, stop ≈ 48–49k)
    orch._check_open_positions(1.0, "BTC/USDT")

    assert len(orch._open_positions) == 0
    assert len(ledger.get_events("position_closed")) == 1

    calc = PortfolioMetricsCalculator(ledger, 10_000.0)
    m = calc.compute(period="30d")
    assert m.open_positions == 0


@pytest.mark.asyncio
async def test_circuit_breaker_sees_loss_after_close(tmp_path):
    orch, ledger = _make_orch(tmp_path)

    await orch.analyze_and_trade("BTC/USDT")
    initial_loss = orch.circuit_breaker._daily_loss_pct

    orch._check_open_positions(1.0, "BTC/USDT")  # forces stop-loss close

    assert orch.circuit_breaker._daily_loss_pct < initial_loss
