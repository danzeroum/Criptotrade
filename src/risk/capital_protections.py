"""Capital protection rules based on drawdown thresholds.

Graham (*The Intelligent Investor*): never let a bad day become a bad week.
Automatic drawdown guards force discipline even when emotions push the other way.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DrawdownStatus(Enum):
    OK = "ok"
    WARN = "warn"            # approaching daily limit
    DAILY_PAUSE = "daily_pause"      # daily limit hit → pause for the day
    WEEKLY_REDUCED = "weekly_reduced"  # weekly limit hit → halve position sizes
    MONTHLY_SUSPEND = "monthly_suspend"  # monthly limit hit → suspend until review


@dataclass
class ProtectionResult:
    status: DrawdownStatus
    message: str
    size_multiplier: float  # 1.0 = normal, 0.5 = halved, 0.0 = blocked
    can_trade: bool


class CapitalProtections:
    """Enforces automatic drawdown-based trading pauses.

    Thresholds (from risk_params.yaml):
      - Daily:   -3%  → pause for the day
      - Weekly:  -6%  → halve position sizes
      - Monthly: -15% → suspend trading until manual review
    """

    DAILY_LIMIT_PCT: float = 3.0
    WEEKLY_LIMIT_PCT: float = 6.0
    MONTHLY_LIMIT_PCT: float = 15.0
    DAILY_WARN_PCT: float = 2.4   # 80% of daily limit

    def check(
        self,
        daily_pnl_pct: float | None = None,
        weekly_pnl_pct: float | None = None,
        monthly_pnl_pct: float | None = None,
    ) -> ProtectionResult:
        """Return the most severe protection triggered.

        Args:
            daily_pnl_pct: Today's P&L as a percentage of capital (negative = loss).
            weekly_pnl_pct: This week's P&L percentage.
            monthly_pnl_pct: This month's P&L percentage.

        Returns:
            ProtectionResult with status, message, and trading permission.
        """
        # Monthly is the most severe — check first
        if monthly_pnl_pct is not None and monthly_pnl_pct <= -self.MONTHLY_LIMIT_PCT:
            msg = (
                f"Monthly drawdown {monthly_pnl_pct:.1f}% hit -{self.MONTHLY_LIMIT_PCT}% limit. "
                "Trading SUSPENDED — manual review required."
            )
            logger.critical(msg)
            return ProtectionResult(
                status=DrawdownStatus.MONTHLY_SUSPEND,
                message=msg,
                size_multiplier=0.0,
                can_trade=False,
            )

        if weekly_pnl_pct is not None and weekly_pnl_pct <= -self.WEEKLY_LIMIT_PCT:
            msg = (
                f"Weekly drawdown {weekly_pnl_pct:.1f}% hit -{self.WEEKLY_LIMIT_PCT}% limit. "
                "Position sizes halved for the remainder of the week."
            )
            logger.warning(msg)
            return ProtectionResult(
                status=DrawdownStatus.WEEKLY_REDUCED,
                message=msg,
                size_multiplier=0.5,
                can_trade=True,
            )

        if daily_pnl_pct is not None and daily_pnl_pct <= -self.DAILY_LIMIT_PCT:
            msg = (
                f"Daily drawdown {daily_pnl_pct:.1f}% hit -{self.DAILY_LIMIT_PCT}% limit. "
                "Trading PAUSED for today."
            )
            logger.warning(msg)
            return ProtectionResult(
                status=DrawdownStatus.DAILY_PAUSE,
                message=msg,
                size_multiplier=0.0,
                can_trade=False,
            )

        if daily_pnl_pct is not None and daily_pnl_pct <= -self.DAILY_WARN_PCT:
            msg = (
                f"Daily drawdown {daily_pnl_pct:.1f}% approaching -{self.DAILY_LIMIT_PCT}% limit."
            )
            logger.info(msg)
            return ProtectionResult(
                status=DrawdownStatus.WARN,
                message=msg,
                size_multiplier=1.0,
                can_trade=True,
            )

        return ProtectionResult(
            status=DrawdownStatus.OK,
            message="",
            size_multiplier=1.0,
            can_trade=True,
        )
