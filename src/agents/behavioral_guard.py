"""Behavioral Guard for detecting trading psychology traps.

Douglas (*Trading in the Zone*): "95% of trading errors come from attitude,
not analysis. The market doesn't care about your emotional state."

Detects:
  - Revenge trading: sizing up after losses (dangerous over-leveraging)
  - Euphoria: sizing up after wins (overconfidence after lucky streak)
  - Overconfidence: expected confidence far above historical win rate
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Thresholds
REVENGE_LOSS_STREAK = 2          # consecutive losses that trigger revenge check
REVENGE_SIZE_MULTIPLIER = 1.50   # 50% bigger than average recent size
EUPHORIA_WIN_STREAK = 3          # consecutive wins that trigger euphoria check
EUPHORIA_SIZE_MULTIPLIER = 1.20  # 20% bigger than average recent size
OVERCONFIDENCE_MARGIN = 0.15     # signal confidence > win_rate + margin


@dataclass
class BehavioralAlert:
    """Result of a behavioral check."""
    detected: bool
    kind: Optional[str] = None          # "revenge_trading" | "euphoria" | "overconfidence"
    message: str = ""
    action: Optional[str] = None        # "reduce_size" | "force_kelly_half" | "cap_confidence"
    recommended_size_multiplier: float = 1.0
    recommended_confidence_cap: Optional[float] = None


class BehavioralGuard:
    """Check a proposed trade against recent trade history for psychology traps.

    Douglas: The goal is not to be right; it is to trade well. Behavioral
    traps (revenge, euphoria, overconfidence) are the primary cause of
    account blow-ups that have nothing to do with market analysis.
    """

    def check(
        self,
        new_trade: Dict[str, Any],
        trade_history: List[Dict[str, Any]],
        *,
        win_rate: Optional[float] = None,
    ) -> BehavioralAlert:
        """Analyse the proposed trade in the context of recent history.

        Args:
            new_trade: The proposed trade dict. Expected keys:
                ``position_size_pct`` (float), ``confidence`` (float, optional).
            trade_history: Recent closed trades, newest first. Each dict should
                have ``pnl`` (float) and ``position_size_pct`` (float).
            win_rate: Historical win rate [0, 1]. Used for overconfidence check.
                If None, the overconfidence check is skipped.

        Returns:
            BehavioralAlert describing any trap detected (or ``detected=False``).
        """
        if not trade_history:
            return BehavioralAlert(detected=False)

        new_size = float(new_trade.get("position_size_pct", 0.0))
        new_confidence = new_trade.get("confidence")

        # Compute recent average size for comparison
        recent_sizes = [float(t.get("position_size_pct", 0.0)) for t in trade_history[:10] if t.get("position_size_pct")]
        avg_recent_size = sum(recent_sizes) / len(recent_sizes) if recent_sizes else 0.0

        # --- Revenge Trading check ---
        consecutive_losses = self._count_streak(trade_history, win=False)
        if consecutive_losses >= REVENGE_LOSS_STREAK and avg_recent_size > 0:
            if new_size >= avg_recent_size * REVENGE_SIZE_MULTIPLIER:
                msg = (
                    f"Revenge trading detected: {consecutive_losses} consecutive losses, "
                    f"proposed size {new_size:.1f}% vs avg {avg_recent_size:.1f}%"
                )
                logger.warning("BehavioralGuard: %s", msg)
                return BehavioralAlert(
                    detected=True,
                    kind="revenge_trading",
                    message=msg,
                    action="reduce_size",
                    recommended_size_multiplier=0.5,
                )

        # --- Euphoria check ---
        consecutive_wins = self._count_streak(trade_history, win=True)
        if consecutive_wins >= EUPHORIA_WIN_STREAK and avg_recent_size > 0:
            if new_size >= avg_recent_size * EUPHORIA_SIZE_MULTIPLIER:
                msg = (
                    f"Euphoria detected: {consecutive_wins} consecutive wins, "
                    f"proposed size {new_size:.1f}% vs avg {avg_recent_size:.1f}%"
                )
                logger.warning("BehavioralGuard: %s", msg)
                return BehavioralAlert(
                    detected=True,
                    kind="euphoria",
                    message=msg,
                    action="force_kelly_half",
                    recommended_size_multiplier=0.5,
                )

        # --- Overconfidence check ---
        if win_rate is not None and new_confidence is not None:
            if new_confidence > win_rate + OVERCONFIDENCE_MARGIN:
                msg = (
                    f"Overconfidence detected: signal confidence {new_confidence:.2f} "
                    f">> historical win rate {win_rate:.2f}"
                )
                logger.info("BehavioralGuard: %s", msg)
                return BehavioralAlert(
                    detected=True,
                    kind="overconfidence",
                    message=msg,
                    action="cap_confidence",
                    recommended_size_multiplier=1.0,
                    recommended_confidence_cap=win_rate,
                )

        return BehavioralAlert(detected=False)

    @staticmethod
    def _count_streak(trades: List[Dict[str, Any]], win: bool) -> int:
        """Count leading consecutive wins or losses in trade history (newest first)."""
        count = 0
        for t in trades:
            pnl = t.get("pnl", 0.0)
            if win and pnl > 0:
                count += 1
            elif not win and pnl < 0:
                count += 1
            else:
                break
        return count
