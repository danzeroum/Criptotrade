"""Portfolio metrics engine.

Computes the KPIs the dashboard needs (Sharpe ratio, win rate, max drawdown,
P&L, exposure, open positions) from the events recorded by
:class:`src.core.ledger.TradingLedger`.

Design notes
------------
* **Pure and decoupled.** This module does not import application ``settings``
  (which has import-time side effects); ``initial_capital`` is injected. That
  keeps the engine trivially unit-testable with a synthetic ledger.
* **Honest about missing data.** Ratios that need a minimum sample (Sharpe needs
  >= 2 days; profit factor needs at least one loss) return ``None`` instead of a
  fabricated number. Callers/UI should render ``None`` as "Sem dados", never as a
  misleading ``0`` or ``--``.
* **Realised vs open.** Realised metrics come from ``position_closed`` events.
  Open positions and exposure reflect the operational ``open_positions`` store
  (current state) — not a replay of un-closed ``order_fill`` events, which would
  inflate the count whenever a fill has no matching close recorded.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from src.core.ledger import TradingLedger

# Crypto trades 24/7, so daily returns are annualised over 365 days.
TRADING_DAYS_PER_YEAR = 365

_PERIOD_DAYS: Dict[str, Optional[int]] = {
    "1d": 1,
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "all": None,
}


@dataclass
class PortfolioMetrics:
    """Snapshot of portfolio performance over a period.

    Ratio fields are ``Optional``: ``None`` means "not enough data to compute",
    which is semantically different from a real ``0.0``.
    """

    sharpe_ratio: Optional[float]
    win_rate: Optional[float]
    max_drawdown: float
    profit_factor: Optional[float]
    total_trades: int
    open_positions: int
    portfolio_value_usdt: float
    pnl_period_usdt: float
    pnl_period_pct: float
    exposure_pct: float
    initial_capital_usdt: float
    period: str
    calculated_at: str
    has_data: bool

    def to_dict(self) -> Dict[str, Any]:
        """Serialise for the API/dashboard layer."""
        return asdict(self)


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp, tolerating a trailing ``Z``."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class PortfolioMetricsCalculator:
    """Compute :class:`PortfolioMetrics` from a :class:`TradingLedger`."""

    def __init__(self, ledger: TradingLedger, initial_capital: float = 10_000.0) -> None:
        self.ledger = ledger
        self.initial_capital = float(initial_capital)

    # ------------------------------------------------------------------ public
    def compute(
        self,
        period: str = "all",
        now: Optional[datetime] = None,
        symbol: Optional[str] = None,
    ) -> PortfolioMetrics:
        """Compute metrics over ``period`` (one of ``1d/7d/30d/90d/all``).

        When ``symbol`` is given, every figure (P&L, value, exposure, ratios) is
        scoped to that pair — a consistent per-symbol sub-portfolio. ``None``
        (the default) keeps the portfolio-wide behaviour.
        """
        if period not in _PERIOD_DAYS:
            raise ValueError(f"Unknown period {period!r}; expected one of {list(_PERIOD_DAYS)}")

        now = now or datetime.now(timezone.utc)
        entries = self.ledger.read_all()

        closed = self._with_timestamps(entries, "position_closed")
        open_positions = self._operational_open_positions()

        if symbol:
            sym = symbol.upper()
            closed = [c for c in closed if str(c.get("symbol", "")).upper() == sym]
            open_positions = [p for p in open_positions if str(p.get("symbol", "")).upper() == sym]

        cutoff = self._cutoff(period, now)
        in_period = [c for c in closed if cutoff is None or (c["_ts"] and c["_ts"] >= cutoff)]

        # Realised P&L across *all* closed trades drives the portfolio value;
        # the period filter only scopes the period-specific figures.
        total_pnl_all = sum(c["pnl"] for c in closed)
        pnl_period = sum(c["pnl"] for c in in_period)
        portfolio_value = self.initial_capital + total_pnl_all

        pnls_period = [c["pnl"] for c in in_period]
        wins = [p for p in pnls_period if p > 0]
        losses = [p for p in pnls_period if p < 0]

        open_notional = sum(p["notional"] for p in open_positions)
        exposure_pct = (open_notional / portfolio_value) if portfolio_value > 0 else 0.0

        return PortfolioMetrics(
            sharpe_ratio=self._sharpe(in_period),
            win_rate=(len(wins) / len(pnls_period)) if pnls_period else None,
            max_drawdown=self._max_drawdown(closed),
            profit_factor=self._profit_factor(wins, losses),
            total_trades=len(in_period),
            open_positions=len(open_positions),
            portfolio_value_usdt=round(portfolio_value, 2),
            pnl_period_usdt=round(pnl_period, 2),
            pnl_period_pct=round(pnl_period / self.initial_capital, 6) if self.initial_capital else 0.0,
            exposure_pct=round(exposure_pct, 6),
            initial_capital_usdt=self.initial_capital,
            period=period,
            calculated_at=now.isoformat(),
            has_data=bool(closed) or bool(open_positions),
        )

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _cutoff(period: str, now: datetime) -> Optional[datetime]:
        days = _PERIOD_DAYS[period]
        return None if days is None else now - timedelta(days=days)

    def _with_timestamps(self, entries: List[Dict[str, Any]], event_type: str) -> List[Dict[str, Any]]:
        """Return ``data`` dicts for ``event_type`` with a parsed ``_ts`` attached.

        The close timestamp is the ledger entry's own timestamp (when it was
        recorded), giving a chronological ordering for the equity curve.
        """
        out: List[Dict[str, Any]] = []
        for e in entries:
            if e.get("event_type") != event_type:
                continue
            data = dict(e["data"])
            data["_ts"] = _parse_ts(e.get("timestamp"))
            out.append(data)
        # Stable chronological order (entries without a ts keep append order).
        out.sort(key=lambda d: (d["_ts"] is None, d["_ts"] or datetime.min.replace(tzinfo=timezone.utc)))
        return out

    def _operational_open_positions(self) -> List[Dict[str, Any]]:
        """Current open positions from the operational ``open_positions`` store.

        The store (maintained by the orchestrator: upsert on open, delete on
        close) is the source of truth for what is open *now*. A replay of
        ``order_fill`` events without a matching ``position_closed`` is not — a
        fill whose close was never recorded would stay "open" forever. Each entry
        carries ``symbol`` and a computed ``notional`` for exposure.
        """
        from src.orchestration.position_store import PositionStore

        positions = PositionStore(lambda: self.ledger.db_path).load_all()
        out: List[Dict[str, Any]] = []
        for order_id, p in positions.items():
            entry_price = p.get("entry_price") or 0.0
            quantity = p.get("quantity") or 0.0
            out.append(
                {
                    "order_id": order_id,
                    "symbol": p.get("symbol"),
                    "notional": entry_price * quantity,
                }
            )
        return out

    def _max_drawdown(self, closed: List[Dict[str, Any]]) -> float:
        """Largest peak-to-trough drop of the equity curve, as a ratio <= 0."""
        if not closed:
            return 0.0
        equity = self.initial_capital
        peak = equity
        max_dd = 0.0
        for trade in closed:  # already chronological
            equity += trade["pnl"]
            peak = max(peak, equity)
            if peak > 0:
                drawdown = (equity - peak) / peak
                max_dd = min(max_dd, drawdown)
        return round(max_dd, 6)

    def _sharpe(self, closed: List[Dict[str, Any]]) -> Optional[float]:
        """Annualised Sharpe ratio from daily equity returns.

        Needs >= 2 distinct UTC days of closed trades. Returns ``None`` when the
        sample is too small or has zero variance (undefined ratio).
        """
        if len(closed) < 2:
            return None

        # Aggregate P&L by UTC date.
        daily_pnl: Dict[Any, float] = {}
        for trade in closed:
            ts = trade.get("_ts")
            day = ts.date() if ts else None
            daily_pnl[day] = daily_pnl.get(day, 0.0) + trade["pnl"]

        days = sorted(d for d in daily_pnl if d is not None)
        if len(days) < 2:
            return None

        returns: List[float] = []
        equity = self.initial_capital
        for day in days:
            if equity <= 0:
                return None
            returns.append(daily_pnl[day] / equity)
            equity += daily_pnl[day]

        if len(returns) < 2:
            return None
        try:
            stdev = statistics.stdev(returns)
        except statistics.StatisticsError:
            return None
        if stdev == 0:
            return None
        sharpe = (statistics.mean(returns) / stdev) * math.sqrt(TRADING_DAYS_PER_YEAR)
        return round(sharpe, 4)

    @staticmethod
    def _profit_factor(wins: List[float], losses: List[float]) -> Optional[float]:
        """Gross profit / gross loss. ``None`` when there are no losses yet."""
        gross_loss = abs(sum(losses))
        if gross_loss == 0:
            return None
        return round(sum(wins) / gross_loss, 4)


__all__ = ["PortfolioMetrics", "PortfolioMetricsCalculator"]
