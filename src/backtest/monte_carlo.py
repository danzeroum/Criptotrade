"""Monte Carlo simulation for strategy robustness assessment.

Davey (*Building Winning Algorithmic Trading Systems*): "Monte Carlo
shuffles the order of your trades randomly N times to reveal how lucky
(or unlucky) the sequence was. If the 5th percentile result is still
positive, the strategy has genuine edge."
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MonteCarloResult:
    """Results of N Monte Carlo simulations."""
    n_simulations: int
    median_final_pnl_pct: float
    percentile_5_pnl_pct: float    # worst-case (p5 < 0 → reject strategy)
    percentile_95_pnl_pct: float
    max_simulated_drawdown: float   # worst drawdown across all simulations
    pct_profitable: float           # fraction of sims that ended positive
    rejected: bool                  # True when p5 < 0


class MonteCarloSimulator:
    """Simulate strategy robustness by shuffling trade order N times.

    Args:
        n_simulations: Number of random shuffles to run.
        random_seed: Optional seed for reproducibility in tests.
    """

    def __init__(self, n_simulations: int = 1000, random_seed: Optional[int] = None) -> None:
        self.n_simulations = n_simulations
        self._rng = random.Random(random_seed)

    def simulate(self, trades_pnl_pct: List[float]) -> MonteCarloResult:
        """Run Monte Carlo on a list of per-trade P&L percentages.

        Args:
            trades_pnl_pct: Historical per-trade returns as fractions
                (e.g. [0.02, -0.01, 0.03, ...]).

        Returns:
            MonteCarloResult with percentile breakdown and rejection flag.
        """
        if not trades_pnl_pct:
            return MonteCarloResult(
                n_simulations=0,
                median_final_pnl_pct=0.0,
                percentile_5_pnl_pct=0.0,
                percentile_95_pnl_pct=0.0,
                max_simulated_drawdown=0.0,
                pct_profitable=0.0,
                rejected=True,
            )

        final_returns: List[float] = []
        max_drawdown_all: float = 0.0

        for _ in range(self.n_simulations):
            shuffled = list(trades_pnl_pct)
            self._rng.shuffle(shuffled)
            equity = 1.0
            peak = 1.0
            for r in shuffled:
                equity *= (1 + r)
                peak = max(peak, equity)
                if peak > 0:
                    dd = (equity - peak) / peak
                    max_drawdown_all = min(max_drawdown_all, dd)

            final_returns.append(equity - 1.0)

        final_returns.sort()
        n = len(final_returns)
        p5 = final_returns[max(0, int(0.05 * n))]
        p50 = final_returns[int(0.50 * n)]
        p95 = final_returns[min(n - 1, int(0.95 * n))]
        pct_profitable = sum(1 for r in final_returns if r > 0) / n

        return MonteCarloResult(
            n_simulations=n,
            median_final_pnl_pct=round(p50, 6),
            percentile_5_pnl_pct=round(p5, 6),
            percentile_95_pnl_pct=round(p95, 6),
            max_simulated_drawdown=round(max_drawdown_all, 4),
            pct_profitable=round(pct_profitable, 4),
            rejected=p5 < 0,
        )
