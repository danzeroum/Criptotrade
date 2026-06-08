"""Backtest engine for strategy evaluation.

References:
  - Pardo (*The Evaluation and Optimization of Trading Strategies*):
    "A backtest is only as valid as its simulation realism. Commission and
    slippage must be modelled honestly."
  - Davey (*Building Winning Algorithmic Trading Systems*):
    "Walk-forward is the only credible test; in-sample optimisation alone
    proves nothing."
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Default simulation costs
DEFAULT_COMMISSION_PCT = 0.001    # 0.1% maker/taker
DEFAULT_SLIPPAGE_BPS = 5         # 5 basis points (0.05%)
WARMUP_CANDLES = 50              # minimum candles before signalling


@dataclass
class BacktestTrade:
    """One simulated round-trip trade."""
    candle_index: int
    action: str          # "BUY" | "SELL"
    entry_price: float
    exit_price: float
    position_size_pct: float
    pnl_usdt: float
    pnl_pct: float
    stop_loss: float | None = None
    take_profit: float | None = None
    exit_reason: str = ""  # "take_profit" | "stop_loss" | "signal"


@dataclass
class BacktestResult:
    """Aggregate results of a backtest run."""
    total_trades: int
    win_rate: float
    total_pnl_usdt: float
    total_pnl_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float | None
    profit_factor: float | None
    avg_win_pct: float
    avg_loss_pct: float
    trades: list[BacktestTrade] = field(default_factory=list)

    @property
    def expectancy(self) -> float:
        """Expected P&L per trade in USD."""
        if not self.trades:
            return 0.0
        return self.total_pnl_usdt / len(self.trades)


class BacktestEngine:
    """Event-driven backtesting engine.

    The engine replays OHLCV candles, calls the strategy on each, simulates
    fills with slippage and commission, and records outcomes.

    Args:
        initial_capital: Starting capital in USD.
        commission_pct: Round-trip commission as a fraction (default 0.001 = 0.1%).
        slippage_bps: Slippage in basis points per fill (default 5 bps).
    """

    def __init__(
        self,
        initial_capital: float = 10_000.0,
        commission_pct: float = DEFAULT_COMMISSION_PCT,
        slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    ) -> None:
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_bps / 10_000.0

    async def run(
        self,
        strategy: Any,
        ohlcv: list[list[float]],
    ) -> BacktestResult:
        """Replay ``ohlcv`` through ``strategy`` and return results.

        The strategy must implement ``async def analyze(market_data) -> dict``
        returning at least ``{"action": "buy"|"sell"|"hold", ...}``.

        A simple exit model is used:
          - If ``take_profit`` is set, exit when close ≥ TP (long) or ≤ TP (short).
          - If ``stop_loss`` is set, exit when close ≤ SL (long) or ≥ SL (short).
          - Otherwise, exit on the next opposing signal.
        """
        if len(ohlcv) < WARMUP_CANDLES + 10:
            logger.warning("Backtest: insufficient data (%d candles)", len(ohlcv))
            return _empty_result()

        capital = self.initial_capital
        trades: list[BacktestTrade] = []
        open_trade: dict[str, Any] | None = None
        equity_curve: list[float] = [capital]

        for i in range(WARMUP_CANDLES, len(ohlcv)):
            candle = ohlcv[i]
            close = float(candle[4])
            high = float(candle[2])
            low = float(candle[3])

            # --- Check open position exits first ---
            if open_trade is not None:
                exit_price, exit_reason = self._check_exits(open_trade, high, low, close)
                if exit_price is not None:
                    trade = self._close_trade(open_trade, exit_price, exit_reason, capital)
                    capital += trade.pnl_usdt
                    trades.append(trade)
                    equity_curve.append(capital)
                    open_trade = None

            # --- Get signal from strategy ---
            if open_trade is None:
                window = ohlcv[max(0, i - 199): i + 1]
                market_data = self._build_market_data(window, close)
                try:
                    result = await strategy.analyze(market_data)
                except Exception as exc:
                    logger.debug("Backtest strategy error at candle %d: %s", i, exc)
                    continue

                action = result.get("action", "hold")
                if action in ("buy", "BUY", "sell", "SELL"):
                    open_trade = self._open_trade(
                        i, action.upper(), close, result, capital
                    )

        # Close any remaining open position at last price
        if open_trade is not None:
            last_close = float(ohlcv[-1][4])
            trade = self._close_trade(open_trade, last_close, "end_of_data", capital)
            capital += trade.pnl_usdt
            trades.append(trade)

        return self._compute_result(trades, equity_curve, capital)

    # ----------------------------------------------------------------- helpers

    def _open_trade(
        self,
        candle_index: int,
        action: str,
        close: float,
        result: dict[str, Any],
        capital: float,
    ) -> dict[str, Any]:
        slipped = close * (1 + self.slippage_pct if action == "BUY" else 1 - self.slippage_pct)
        size_pct = float(result.get("position_size_pct", 2.0))
        return {
            "candle_index": candle_index,
            "action": action,
            "entry_price": round(slipped, 6),
            "position_size_pct": size_pct,
            "stop_loss": result.get("stop_loss"),
            "take_profit": result.get("take_profit"),
            "capital_at_entry": capital,
        }

    def _check_exits(
        self,
        trade: dict[str, Any],
        high: float,
        low: float,
        close: float,
    ) -> tuple[float | None, str]:
        action = trade["action"]
        sl = trade.get("stop_loss")
        tp = trade.get("take_profit")

        if action == "BUY":
            if sl is not None and low <= sl:
                return sl, "stop_loss"
            if tp is not None and high >= tp:
                return tp, "take_profit"
        elif action == "SELL":
            if sl is not None and high >= sl:
                return sl, "stop_loss"
            if tp is not None and low <= tp:
                return tp, "take_profit"

        return None, ""

    def _close_trade(
        self,
        trade: dict[str, Any],
        exit_price: float,
        exit_reason: str,
        capital: float,
    ) -> BacktestTrade:
        action = trade["action"]
        entry = trade["entry_price"]
        size_pct = trade["position_size_pct"]

        slipped_exit = exit_price * (
            1 - self.slippage_pct if action == "BUY" else 1 + self.slippage_pct
        )
        notional = capital * size_pct / 100.0

        if action == "BUY":
            raw_pct = (slipped_exit - entry) / entry
        else:
            raw_pct = (entry - slipped_exit) / entry

        commission = self.commission_pct * 2  # entry + exit
        net_pct = raw_pct - commission

        pnl_usdt = notional * net_pct

        return BacktestTrade(
            candle_index=trade["candle_index"],
            action=action,
            entry_price=entry,
            exit_price=round(slipped_exit, 6),
            position_size_pct=size_pct,
            pnl_usdt=round(pnl_usdt, 4),
            pnl_pct=round(net_pct, 6),
            stop_loss=trade.get("stop_loss"),
            take_profit=trade.get("take_profit"),
            exit_reason=exit_reason,
        )

    @staticmethod
    def _build_market_data(window: list[list[float]], close: float) -> dict[str, Any]:
        return {
            "current_price": close,
            "rsi": 50,
            "macd_histogram": 0,
            "at_bollinger_lower": False,
            "ma_20": close,
            "ma_50": close,
            "volume_24h": float(window[-1][5]) if window else 0,
            "avg_volume": 1,
            "_raw_ohlcv": window,
        }

    def _compute_result(
        self,
        trades: list[BacktestTrade],
        equity_curve: list[float],
        final_capital: float,
    ) -> BacktestResult:
        n = len(trades)
        if n == 0:
            return _empty_result()

        wins = [t for t in trades if t.pnl_usdt > 0]
        losses = [t for t in trades if t.pnl_usdt <= 0]

        win_rate = len(wins) / n
        total_pnl = sum(t.pnl_usdt for t in trades)
        total_pnl_pct = total_pnl / self.initial_capital

        avg_win_pct = sum(t.pnl_pct for t in wins) / len(wins) if wins else 0.0
        avg_loss_pct = sum(t.pnl_pct for t in losses) / len(losses) if losses else 0.0

        gross_profit = sum(t.pnl_usdt for t in wins)
        gross_loss = abs(sum(t.pnl_usdt for t in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

        max_dd = _max_drawdown(equity_curve)
        sharpe = _sharpe(trades, self.initial_capital)

        return BacktestResult(
            total_trades=n,
            win_rate=round(win_rate, 4),
            total_pnl_usdt=round(total_pnl, 2),
            total_pnl_pct=round(total_pnl_pct, 6),
            max_drawdown_pct=round(max_dd, 4),
            sharpe_ratio=sharpe,
            profit_factor=round(profit_factor, 4) if profit_factor else None,
            avg_win_pct=round(avg_win_pct, 6),
            avg_loss_pct=round(avg_loss_pct, 6),
            trades=trades,
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _empty_result() -> BacktestResult:
    return BacktestResult(
        total_trades=0,
        win_rate=0.0,
        total_pnl_usdt=0.0,
        total_pnl_pct=0.0,
        max_drawdown_pct=0.0,
        sharpe_ratio=None,
        profit_factor=None,
        avg_win_pct=0.0,
        avg_loss_pct=0.0,
        trades=[],
    )


def _max_drawdown(equity: list[float]) -> float:
    if len(equity) < 2:
        return 0.0
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        if peak > 0:
            dd = (v - peak) / peak
            max_dd = min(max_dd, dd)
    return max_dd


def _sharpe(trades: list[BacktestTrade], initial_capital: float) -> float | None:
    if len(trades) < 2:
        return None
    returns = [t.pnl_usdt / initial_capital for t in trades]
    mean_r = sum(returns) / len(returns)
    variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
    if variance <= 0:
        return None
    std_r = variance ** 0.5
    return round(mean_r / std_r * (252 ** 0.5), 4)  # annualised assuming daily trades
