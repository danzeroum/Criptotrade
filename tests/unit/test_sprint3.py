"""Unit tests for Sprint 3: Trade Journal, Backtest Engine, Monte Carlo, Walk-Forward."""
from __future__ import annotations

import math
import pytest

from src.journal.trade_journal import TradeJournal, TradeEntry, JournalStats
from src.backtest.engine import BacktestEngine, BacktestResult
from src.backtest.monte_carlo import MonteCarloSimulator
from src.backtest.validator import WalkForwardValidator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int, base: float = 50000.0, amplitude: float = 0.02) -> list:
    candles = []
    for i in range(n):
        close = base * (1 + amplitude * math.sin(2 * math.pi * i / 20))
        open_ = base * (1 + amplitude * math.sin(2 * math.pi * (i - 1) / 20))
        high = max(open_, close) * 1.002
        low = min(open_, close) * 0.998
        candles.append([i * 3600000, open_, high, low, close, 1000.0])
    return candles


class _AlwaysBuyStrategy:
    """Minimal test strategy: always BUY with fixed stop/target."""
    async def analyze(self, market_data):
        price = market_data.get("current_price", 50000)
        return {
            "action": "buy",
            "position_size_pct": 2.0,
            "stop_loss": price * 0.97,
            "take_profit": price * 1.06,
            "confidence": 0.75,
        }


class _AlwaysHoldStrategy:
    """Strategy that never trades."""
    async def analyze(self, market_data):
        return {"action": "hold"}


# ---------------------------------------------------------------------------
# TradeJournal
# ---------------------------------------------------------------------------

class TestTradeJournal:
    def test_record_and_retrieve(self, tmp_path):
        journal = TradeJournal(str(tmp_path / "journal.json"))
        entry = TradeEntry(order_id="ord1", symbol="BTC/USDT", action="BUY", entry_price=50000)
        journal.record_entry(entry)
        retrieved = journal.get_entry("ord1")
        assert retrieved is not None
        assert retrieved.symbol == "BTC/USDT"

    def test_close_trade(self, tmp_path):
        journal = TradeJournal(str(tmp_path / "journal.json"))
        entry = TradeEntry(order_id="ord2", symbol="BTC/USDT", action="BUY", entry_price=50000)
        journal.record_entry(entry)
        closed = journal.close_trade("ord2", exit_price=51000, plan_followed=True)
        assert closed is not None
        assert closed.pnl_pct == pytest.approx(0.02)
        assert closed.plan_followed is True

    def test_stats_empty(self, tmp_path):
        journal = TradeJournal(str(tmp_path / "journal.json"))
        stats = journal.stats()
        assert stats.total_trades == 0

    def test_stats_with_trades(self, tmp_path):
        journal = TradeJournal(str(tmp_path / "journal.json"))
        # 2 wins, 1 loss
        for i, (entry_p, exit_p) in enumerate([(50000, 51000), (50000, 49000), (50000, 51500)]):
            e = TradeEntry(order_id=f"ord{i}", symbol="BTC/USDT", action="BUY", entry_price=entry_p)
            journal.record_entry(e)
            journal.close_trade(f"ord{i}", exit_p, plan_followed=(i != 1))

        stats = journal.stats()
        assert stats.total_trades == 3
        assert stats.win_rate == pytest.approx(2 / 3)
        assert stats.plan_follow_rate is not None

    def test_plan_adherence_correlation(self, tmp_path):
        journal = TradeJournal(str(tmp_path / "journal.json"))
        # Plan followed → wins; deviated → losses
        for i in range(4):
            e = TradeEntry(order_id=f"o{i}", symbol="BTC/USDT", action="BUY", entry_price=50000,
                           emotional_state_before=7 if i < 2 else 3)
            journal.record_entry(e)
            if i < 2:
                journal.close_trade(f"o{i}", 51000, plan_followed=True)
            else:
                journal.close_trade(f"o{i}", 49000, plan_followed=False)

        stats = journal.stats()
        # Followed plan → positive avg; deviated → negative avg
        assert stats.avg_pnl_when_plan_followed is not None
        assert stats.avg_pnl_when_plan_deviated is not None
        assert (stats.avg_pnl_when_plan_followed or 0) > (stats.avg_pnl_when_plan_deviated or 0)

    def test_sell_trade_pnl(self, tmp_path):
        journal = TradeJournal(str(tmp_path / "journal.json"))
        e = TradeEntry(order_id="s1", symbol="BTC/USDT", action="SELL", entry_price=50000)
        journal.record_entry(e)
        closed = journal.close_trade("s1", exit_price=49000)
        assert (closed.pnl_pct or 0) > 0  # sell at 50k, cover at 49k = profit

    def test_open_entries_listed(self, tmp_path):
        journal = TradeJournal(str(tmp_path / "journal.json"))
        e = TradeEntry(order_id="open1", symbol="ETH/USDT", action="BUY", entry_price=3000)
        journal.record_entry(e)
        open_list = journal.open_entries()
        assert len(open_list) == 1
        assert open_list[0].order_id == "open1"


# ---------------------------------------------------------------------------
# BacktestEngine
# ---------------------------------------------------------------------------

class TestBacktestEngine:
    @pytest.mark.asyncio
    async def test_empty_result_on_insufficient_data(self):
        engine = BacktestEngine()
        result = await engine.run(_AlwaysBuyStrategy(), _make_ohlcv(20))
        assert result.total_trades == 0

    @pytest.mark.asyncio
    async def test_trades_generated(self):
        engine = BacktestEngine()
        ohlcv = _make_ohlcv(200)
        result = await engine.run(_AlwaysBuyStrategy(), ohlcv)
        assert result.total_trades > 0

    @pytest.mark.asyncio
    async def test_no_trades_on_hold_strategy(self):
        engine = BacktestEngine()
        result = await engine.run(_AlwaysHoldStrategy(), _make_ohlcv(200))
        assert result.total_trades == 0

    @pytest.mark.asyncio
    async def test_result_fields_valid(self):
        engine = BacktestEngine()
        result = await engine.run(_AlwaysBuyStrategy(), _make_ohlcv(200))
        if result.total_trades > 0:
            assert 0.0 <= result.win_rate <= 1.0
            assert result.max_drawdown_pct <= 0.0
            assert isinstance(result.total_pnl_usdt, float)

    @pytest.mark.asyncio
    async def test_commission_reduces_pnl(self):
        no_cost = BacktestEngine(commission_pct=0.0, slippage_bps=0)
        with_cost = BacktestEngine(commission_pct=0.001, slippage_bps=5)
        ohlcv = _make_ohlcv(200)
        r_free = await no_cost.run(_AlwaysBuyStrategy(), ohlcv)
        r_cost = await with_cost.run(_AlwaysBuyStrategy(), ohlcv)
        if r_free.total_trades > 0 and r_cost.total_trades > 0:
            assert r_free.total_pnl_usdt >= r_cost.total_pnl_usdt


# ---------------------------------------------------------------------------
# MonteCarloSimulator
# ---------------------------------------------------------------------------

class TestMonteCarlo:
    def test_empty_trades_returns_rejected(self):
        mc = MonteCarloSimulator(n_simulations=100)
        result = mc.simulate([])
        assert result.rejected is True

    def test_all_winning_trades_not_rejected(self):
        mc = MonteCarloSimulator(n_simulations=200, random_seed=42)
        trades = [0.02] * 50  # 50 trades each +2%
        result = mc.simulate(trades)
        assert result.rejected is False
        assert result.percentile_5_pnl_pct > 0

    def test_losing_strategy_rejected(self):
        mc = MonteCarloSimulator(n_simulations=200, random_seed=42)
        trades = [-0.01] * 30  # all losing
        result = mc.simulate(trades)
        assert result.rejected is True

    def test_percentile_ordering(self):
        mc = MonteCarloSimulator(n_simulations=500, random_seed=7)
        trades = [0.01, -0.005, 0.02, -0.01, 0.015] * 10
        result = mc.simulate(trades)
        assert result.percentile_5_pnl_pct <= result.median_final_pnl_pct <= result.percentile_95_pnl_pct

    def test_pct_profitable_range(self):
        mc = MonteCarloSimulator(n_simulations=100, random_seed=1)
        result = mc.simulate([0.01, -0.005] * 20)
        assert 0.0 <= result.pct_profitable <= 1.0

    def test_n_simulations_respected(self):
        mc = MonteCarloSimulator(n_simulations=50, random_seed=99)
        result = mc.simulate([0.01] * 10)
        assert result.n_simulations == 50


# ---------------------------------------------------------------------------
# WalkForwardValidator
# ---------------------------------------------------------------------------

class TestWalkForwardValidator:
    @pytest.mark.asyncio
    async def test_insufficient_data_returns_invalid(self):
        validator = WalkForwardValidator(window_size=252, test_size=63, min_windows=3)
        result = await validator.validate(_AlwaysBuyStrategy(), _make_ohlcv(100))
        assert result.valid is False
        assert "windows" in result.rejection_reason.lower() or "candles" in result.rejection_reason.lower()

    @pytest.mark.asyncio
    async def test_enough_data_runs_windows(self):
        validator = WalkForwardValidator(window_size=100, test_size=30, min_windows=2)
        ohlcv = _make_ohlcv(300)
        result = await validator.validate(_AlwaysBuyStrategy(), ohlcv)
        assert result.n_windows >= 2

    @pytest.mark.asyncio
    async def test_result_has_oos_trade_count(self):
        validator = WalkForwardValidator(window_size=80, test_size=30, min_windows=2)
        ohlcv = _make_ohlcv(250)
        result = await validator.validate(_AlwaysBuyStrategy(), ohlcv)
        assert isinstance(result.total_out_of_sample_trades, int)

    @pytest.mark.asyncio
    async def test_hold_strategy_gives_zero_trades(self):
        validator = WalkForwardValidator(window_size=80, test_size=30, min_windows=2)
        ohlcv = _make_ohlcv(250)
        result = await validator.validate(_AlwaysHoldStrategy(), ohlcv)
        assert result.total_out_of_sample_trades == 0
