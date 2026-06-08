"""Walk-forward validation for strategy robustness.

Pardo (*The Evaluation and Optimization of Trading Strategies*):
"Walk-forward analysis is the only test that credibly demonstrates
out-of-sample performance.  In-sample optimisation is curve-fitting."

Davey (*Building Winning Algorithmic Trading Systems*):
"If a strategy's out-of-sample Sharpe deviates more than 30% from its
in-sample Sharpe across windows, the in-sample results are suspect."
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional

from .engine import BacktestEngine, BacktestResult

logger = logging.getLogger(__name__)

# Rejection threshold: if out-of-sample Sharpe deviates > 30% from in-sample mean
MAX_SHARPE_DEVIATION = 0.30


@dataclass
class WindowResult:
    window_index: int
    train_start: int      # candle index
    train_end: int
    test_start: int
    test_end: int
    train_result: BacktestResult
    test_result: BacktestResult


@dataclass
class WalkForwardResult:
    n_windows: int
    valid: bool           # False when Sharpe deviation is too high
    sharpe_deviation: Optional[float]
    avg_out_of_sample_sharpe: Optional[float]
    avg_in_sample_sharpe: Optional[float]
    total_out_of_sample_trades: int
    out_of_sample_win_rate: float
    window_results: List[WindowResult] = field(default_factory=list)
    rejection_reason: str = ""


class WalkForwardValidator:
    """Validate a strategy with walk-forward windows.

    Each window trains on ``window_size`` candles and tests on
    ``test_size`` candles. Requires at least ``min_windows`` windows.

    Args:
        window_size: Training window in candles.
        test_size: Testing window in candles.
        min_windows: Minimum windows required for a valid result.
    """

    def __init__(
        self,
        window_size: int = 252,
        test_size: int = 63,
        min_windows: int = 3,
        initial_capital: float = 10_000.0,
    ) -> None:
        self.window_size = window_size
        self.test_size = test_size
        self.min_windows = min_windows
        self.initial_capital = initial_capital

    async def validate(
        self,
        strategy: Any,
        ohlcv: list,
    ) -> WalkForwardResult:
        """Run walk-forward validation.

        Args:
            strategy: Strategy instance with ``async analyze(market_data)`` method.
            ohlcv: Full OHLCV dataset.

        Returns:
            WalkForwardResult indicating whether the strategy is robust.
        """
        total_candles = len(ohlcv)
        step = self.test_size
        windows = []

        start = 0
        while start + self.window_size + self.test_size <= total_candles:
            train_end = start + self.window_size
            test_end = train_end + self.test_size
            windows.append((start, train_end, test_end))
            start += step

        if len(windows) < self.min_windows:
            return WalkForwardResult(
                n_windows=len(windows),
                valid=False,
                sharpe_deviation=None,
                avg_out_of_sample_sharpe=None,
                avg_in_sample_sharpe=None,
                total_out_of_sample_trades=0,
                out_of_sample_win_rate=0.0,
                rejection_reason=(
                    f"Need {self.min_windows} windows, got {len(windows)} "
                    f"(need {self.min_windows * (self.window_size + self.test_size)} candles, "
                    f"have {total_candles})"
                ),
            )

        engine = BacktestEngine(initial_capital=self.initial_capital)
        window_results = []

        for idx, (tr_start, tr_end, te_end) in enumerate(windows):
            train_ohlcv = ohlcv[tr_start:tr_end]
            test_ohlcv = ohlcv[tr_end - 50: te_end]  # include 50 warmup candles

            try:
                train_result = await engine.run(strategy, train_ohlcv)
                test_result = await engine.run(strategy, test_ohlcv)
            except Exception as exc:
                logger.warning("WalkForward window %d error: %s", idx, exc)
                continue

            window_results.append(WindowResult(
                window_index=idx,
                train_start=tr_start,
                train_end=tr_end,
                test_start=tr_end,
                test_end=te_end,
                train_result=train_result,
                test_result=test_result,
            ))

        if not window_results:
            return WalkForwardResult(
                n_windows=0,
                valid=False,
                sharpe_deviation=None,
                avg_out_of_sample_sharpe=None,
                avg_in_sample_sharpe=None,
                total_out_of_sample_trades=0,
                out_of_sample_win_rate=0.0,
                rejection_reason="No windows completed successfully",
            )

        in_sharpes = [
            w.train_result.sharpe_ratio
            for w in window_results
            if w.train_result.sharpe_ratio is not None
        ]
        out_sharpes = [
            w.test_result.sharpe_ratio
            for w in window_results
            if w.test_result.sharpe_ratio is not None
        ]

        avg_in = sum(in_sharpes) / len(in_sharpes) if in_sharpes else None
        avg_out = sum(out_sharpes) / len(out_sharpes) if out_sharpes else None

        # Sharpe deviation check
        deviation = None
        if avg_in is not None and avg_out is not None and avg_in != 0:
            deviation = abs(avg_in - avg_out) / abs(avg_in)

        valid = True
        rejection_reason = ""
        if deviation is not None and deviation > MAX_SHARPE_DEVIATION:
            valid = False
            rejection_reason = (
                f"Sharpe deviation {deviation:.1%} > {MAX_SHARPE_DEVIATION:.0%} — "
                "likely overfitting"
            )

        total_oos_trades = sum(w.test_result.total_trades for w in window_results)
        all_oos_wins = sum(
            round(w.test_result.win_rate * w.test_result.total_trades)
            for w in window_results
        )
        oos_win_rate = all_oos_wins / total_oos_trades if total_oos_trades > 0 else 0.0

        return WalkForwardResult(
            n_windows=len(window_results),
            valid=valid,
            sharpe_deviation=round(deviation, 4) if deviation else None,
            avg_in_sample_sharpe=round(avg_in, 4) if avg_in else None,
            avg_out_of_sample_sharpe=round(avg_out, 4) if avg_out else None,
            total_out_of_sample_trades=total_oos_trades,
            out_of_sample_win_rate=round(oos_win_rate, 4),
            window_results=window_results,
            rejection_reason=rejection_reason,
        )
