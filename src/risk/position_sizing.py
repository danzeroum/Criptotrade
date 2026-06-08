"""Position sizing using Kelly Criterion and Risk of Ruin calculations.

References:
  - Douglas, *Trading in the Zone*: "Never risk more than you can afford to lose."
  - Murphy, *Technical Analysis*: "Stop distance defines the bet size, not the other way around."
  - Full Kelly is too aggressive for live trading; fractional Kelly (0.25×f*) is standard.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Fraction of full Kelly to use — reduces variance significantly.
KELLY_FRACTION = 0.25

# Hard limits regardless of what Kelly recommends.
MIN_POSITION_PCT = 0.5
MAX_POSITION_PCT = 5.0

# Minimum trades before Kelly has statistical meaning.
MIN_SAMPLE_FOR_KELLY = 30


def risk_of_ruin(win_rate: float, bet_fraction: float) -> float:
    """Estimate probability of total ruin.

    Uses the classical formula: RoR = ((1 - edge) / (1 + edge))^(1 / bet_fraction)
    where edge = win_rate - (1 - win_rate) = 2*win_rate - 1.

    Returns a value in [0, 1]. Values above 0.05 (5%) warrant an alert.
    """
    if bet_fraction <= 0 or win_rate <= 0:
        return 1.0
    edge = 2.0 * win_rate - 1.0
    if edge <= 0:
        return 1.0
    base = (1.0 - edge) / (1.0 + edge)
    if base <= 0:
        return 0.0
    # guard against math domain errors (base > 1 can't happen when edge > 0, but clamp anyway)
    if base >= 1.0:
        return 1.0
    try:
        return base ** (1.0 / bet_fraction)
    except (ZeroDivisionError, ValueError):
        return 1.0


@dataclass
class KellyCriterion:
    """Kelly Criterion position sizer.

    Args:
        win_rate: Historical win rate in [0, 1].
        avg_win_pct: Average winning trade return as a percentage (e.g. 3.0 for 3%).
        avg_loss_pct: Average losing trade return as a positive percentage (e.g. 1.5 for 1.5%).
        capital: Total available capital in USD.
        n_trades: Number of historical trades used to compute stats.
    """

    win_rate: float
    avg_win_pct: float
    avg_loss_pct: float
    capital: float = 10_000.0
    n_trades: int = 0

    def full_kelly(self) -> float | None:
        """Full Kelly fraction f* = (p*b - q) / b.

        b = avg_win / avg_loss (win-to-loss ratio)
        p = win_rate
        q = 1 - win_rate

        Returns None when there is insufficient statistical basis.
        """
        if self.n_trades < MIN_SAMPLE_FOR_KELLY:
            return None
        if self.avg_loss_pct <= 0:
            return None

        b = self.avg_win_pct / self.avg_loss_pct
        p = self.win_rate
        q = 1.0 - p

        f = (p * b - q) / b
        return f

    def fractional_kelly(self, fraction: float = KELLY_FRACTION) -> float:
        """Fractional Kelly: fraction × f*, clamped to [MIN, MAX] percent.

        Falls back to a safe default when Kelly is not yet computable.
        """
        f_star = self.full_kelly()
        if f_star is None or f_star <= 0:
            # Not enough data or negative edge → use conservative default
            return MIN_POSITION_PCT

        recommended = f_star * fraction * 100.0  # convert to percentage
        return round(max(MIN_POSITION_PCT, min(MAX_POSITION_PCT, recommended)), 2)

    def ruin_risk(self) -> float:
        """Return the risk-of-ruin given the fractional Kelly bet size."""
        bet_fraction = self.fractional_kelly() / 100.0
        return round(risk_of_ruin(self.win_rate, bet_fraction), 6)


class PositionSizer:
    """Compute position size combining Kelly with Murphy's stop-distance rule.

    Murphy: size = (capital × max_risk%) / stop_distance%
    Kelly: adjust max_risk% based on historical edge.

    The two are reconciled by using Kelly's fractional bet as the risk cap.
    """

    def __init__(
        self,
        capital: float = 10_000.0,
        default_risk_pct: float = 1.0,
        kelly: KellyCriterion | None = None,
    ) -> None:
        self.capital = capital
        self.default_risk_pct = default_risk_pct
        self.kelly = kelly

    def compute(
        self,
        entry_price: float,
        stop_price: float,
        *,
        capital_override: float | None = None,
    ) -> float:
        """Return position size as a percentage of capital.

        Uses Kelly if available and statistically valid; otherwise falls back
        to ``default_risk_pct``.

        Args:
            entry_price: Planned entry price.
            stop_price: Planned stop-loss price.
            capital_override: Use a different capital figure (e.g. current equity).

        Returns:
            Position size in % of capital, clamped to [MIN, MAX].
        """
        capital = capital_override or self.capital

        if entry_price <= 0 or stop_price <= 0 or capital <= 0:
            return MIN_POSITION_PCT

        stop_distance_pct = abs(entry_price - stop_price) / entry_price * 100.0
        if stop_distance_pct <= 0:
            return MIN_POSITION_PCT

        # Determine risk budget: Kelly if available, else default
        if self.kelly is not None:
            risk_budget_pct = self.kelly.fractional_kelly()
        else:
            risk_budget_pct = self.default_risk_pct

        # Murphy's formula: size = risk_budget / stop_distance
        size_pct = risk_budget_pct / stop_distance_pct * 100.0

        clamped = round(max(MIN_POSITION_PCT, min(MAX_POSITION_PCT, size_pct)), 2)

        ror = risk_of_ruin(
            win_rate=self.kelly.win_rate if self.kelly else 0.5,
            bet_fraction=clamped / 100.0,
        )
        if ror > 0.05:
            logger.warning(
                "Risk of ruin %.1f%% exceeds 5%% threshold (size=%.2f%%, capital=$%.0f)",
                ror * 100,
                clamped,
                capital,
            )

        return clamped
