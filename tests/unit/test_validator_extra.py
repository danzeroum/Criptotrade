"""Extra coverage for backtest/validator.py — exception path, empty results, deviation."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.backtest.validator import WalkForwardValidator
from src.backtest.engine import BacktestResult


def _make_result(sharpe: float | None = 1.0, trades: int = 5) -> BacktestResult:
    return BacktestResult(
        total_trades=trades,
        win_rate=0.6,
        total_pnl_usdt=500.0,
        total_pnl_pct=0.05,
        max_drawdown_pct=-0.10,
        sharpe_ratio=sharpe,
        profit_factor=1.5,
        avg_win_pct=0.02,
        avg_loss_pct=-0.01,
    )


def _make_ohlcv(n: int) -> list:
    ts = 1_700_000_000_000
    return [[ts + i * 3600_000, 50_000.0, 50_500.0, 49_500.0, 50_000.0, 100.0] for i in range(n)]


# ── insufficient candles → rejection before any window runs ──────────────────

@pytest.mark.asyncio
async def test_validate_insufficient_candles():
    """Lines 98-112: fewer windows than min_windows → rejection message."""
    validator = WalkForwardValidator(window_size=60, test_size=10, min_windows=5)
    result = await validator.validate(MagicMock(), _make_ohlcv(80))
    assert result.valid is False
    assert result.n_windows < 5


# ── all windows raise → empty window_results ─────────────────────────────────

@pytest.mark.asyncio
async def test_validate_all_windows_raise_returns_invalid():
    """Lines 124-126 + 139: engine.run raises every window → empty results."""
    validator = WalkForwardValidator(window_size=60, test_size=10, min_windows=2)

    with patch("src.backtest.validator.BacktestEngine") as MockEngine:
        mock_engine = MagicMock()
        mock_engine.run = AsyncMock(side_effect=RuntimeError("simulated engine failure"))
        MockEngine.return_value = mock_engine

        result = await validator.validate(MagicMock(), _make_ohlcv(150))

    assert result.valid is False
    assert result.n_windows == 0
    assert "No windows completed" in result.rejection_reason


# ── sharpe deviation too high → rejection ────────────────────────────────────

@pytest.mark.asyncio
async def test_validate_high_sharpe_deviation_rejected():
    """Lines 167 + 172-173: out-of-sample Sharpe deviates > 30% → valid=False."""
    validator = WalkForwardValidator(window_size=60, test_size=10, min_windows=2)

    call_count = 0

    async def alternating_run(strategy, ohlcv):
        nonlocal call_count
        call_count += 1
        # Even calls = train (high sharpe), odd calls = test (very low sharpe)
        return _make_result(sharpe=2.0 if call_count % 2 == 1 else 0.1)

    with patch("src.backtest.validator.BacktestEngine") as MockEngine:
        mock_engine = MagicMock()
        mock_engine.run = alternating_run
        MockEngine.return_value = mock_engine

        result = await validator.validate(MagicMock(), _make_ohlcv(200))

    # avg_in=2.0, avg_out=0.1 → deviation = |2.0-0.1|/|2.0| = 0.95 > 0.30
    assert result.valid is False
    assert "overfitting" in result.rejection_reason.lower()
    assert result.sharpe_deviation is not None


# ── no sharpe in any window → deviation=None → valid ─────────────────────────

@pytest.mark.asyncio
async def test_validate_no_sharpe_ratios_is_valid():
    """Lines 161-162: no sharpe ratios → avg_in=None → deviation=None → valid=True."""
    validator = WalkForwardValidator(window_size=60, test_size=10, min_windows=2)

    with patch("src.backtest.validator.BacktestEngine") as MockEngine:
        mock_engine = MagicMock()
        mock_engine.run = AsyncMock(return_value=_make_result(sharpe=None, trades=0))
        MockEngine.return_value = mock_engine

        result = await validator.validate(MagicMock(), _make_ohlcv(200))

    assert result.sharpe_deviation is None
    assert result.valid is True
