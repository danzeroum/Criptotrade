"""Behavioral trade journal.

Douglas (*Trading in the Zone*): "You need to trade in the 'zone' —
a state of mind where discipline and process override emotion.  A journal
forces reflection and quantifies the cost of deviation."

The journal records not only the financial outcome but the psychological
state and plan adherence that led to it.  Aggregated metrics reveal whether
losses are correlated with emotional states or plan deviations, enabling
measurable improvement of trading discipline.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TradeEntry:
    """One recorded trade with behavioural context.

    All fields with defaults are optional at the time of entry creation.
    They should be filled in before the trade is closed.
    """
    # Identity
    order_id: str
    symbol: str
    action: str          # "BUY" | "SELL"
    entry_price: float
    entry_time: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Setup — what did the analysis say?
    setup: str = ""           # e.g. "Grid long in sideways regime, RSI 47, near S1"
    strategy: str = ""
    regime: str = ""

    # Psychology — Douglas: record state BEFORE entry
    emotional_state_before: int = 5   # 1 (fearful) – 10 (euphoric)
    stop_defined_before_entry: bool = True
    plan_text: str = ""               # written plan before entry

    # Outcome — filled on close
    exit_price: float | None = None
    exit_time: str | None = None
    pnl_usdt: float | None = None
    pnl_pct: float | None = None
    plan_followed: bool | None = None   # was the written plan executed?
    plan_deviation_note: str = ""          # free text when plan_followed=False
    emotional_state_after: int | None = None  # 1-10 after seeing result

    def is_closed(self) -> bool:
        return self.exit_price is not None

    def close(
        self,
        exit_price: float,
        *,
        plan_followed: bool = True,
        deviation_note: str = "",
        emotional_after: int | None = None,
    ) -> None:
        self.exit_price = exit_price
        self.exit_time = datetime.now(UTC).isoformat()
        if self.entry_price > 0:
            if self.action == "BUY":
                self.pnl_pct = (exit_price - self.entry_price) / self.entry_price
            else:
                self.pnl_pct = (self.entry_price - exit_price) / self.entry_price
            self.pnl_usdt = self.pnl_pct * self.entry_price  # per-unit
        self.plan_followed = plan_followed
        self.plan_deviation_note = deviation_note
        self.emotional_state_after = emotional_after


@dataclass
class JournalStats:
    """Aggregated statistics from the journal."""
    total_trades: int
    win_rate: float              # 0-1
    avg_pnl_pct: float
    # Douglas metrics
    avg_pnl_when_plan_followed: float | None
    avg_pnl_when_plan_deviated: float | None
    plan_follow_rate: float | None     # fraction of trades where plan was followed
    avg_emotional_state_before_wins: float | None
    avg_emotional_state_before_losses: float | None
    # Financial
    expectancy_usdt: float       # expected $ per trade


class TradeJournal:
    """Persistent trade journal backed by a JSON file.

    Args:
        journal_path: Path to the JSON file. Defaults to
            ``./data/trade_journal.json`` or the ``JOURNAL_PATH`` env var.
    """

    def __init__(self, journal_path: str | None = None) -> None:
        path_str = journal_path or os.getenv("JOURNAL_PATH", "data/trade_journal.json")
        self._path = Path(path_str)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, TradeEntry] = {}
        self._load()

    # ------------------------------------------------------------------ public

    def record_entry(self, entry: TradeEntry) -> None:
        """Record a new trade entry."""
        self._entries[entry.order_id] = entry
        self._save()
        logger.info(
            "Journal: recorded entry %s %s @ %.2f",
            entry.order_id, entry.symbol, entry.entry_price,
        )

    def close_trade(
        self,
        order_id: str,
        exit_price: float,
        *,
        plan_followed: bool = True,
        deviation_note: str = "",
        emotional_after: int | None = None,
    ) -> TradeEntry | None:
        """Close an open trade and save the outcome."""
        entry = self._entries.get(order_id)
        if entry is None:
            logger.warning("Journal: unknown order_id %s", order_id)
            return None
        entry.close(exit_price, plan_followed=plan_followed,
                    deviation_note=deviation_note, emotional_after=emotional_after)
        self._save()
        logger.info(
            "Journal: closed %s PnL=%.2f%%",
            order_id,
            (entry.pnl_pct or 0) * 100,
        )
        return entry

    def get_entry(self, order_id: str) -> TradeEntry | None:
        return self._entries.get(order_id)

    def all_entries(self) -> list[TradeEntry]:
        return list(self._entries.values())

    def closed_entries(self) -> list[TradeEntry]:
        return [e for e in self._entries.values() if e.is_closed()]

    def open_entries(self) -> list[TradeEntry]:
        return [e for e in self._entries.values() if not e.is_closed()]

    def stats(self) -> JournalStats:
        """Compute aggregated behavioural statistics."""
        closed = self.closed_entries()
        n = len(closed)

        if n == 0:
            return JournalStats(
                total_trades=0,
                win_rate=0.0,
                avg_pnl_pct=0.0,
                avg_pnl_when_plan_followed=None,
                avg_pnl_when_plan_deviated=None,
                plan_follow_rate=None,
                avg_emotional_state_before_wins=None,
                avg_emotional_state_before_losses=None,
                expectancy_usdt=0.0,
            )

        wins = [e for e in closed if (e.pnl_pct or 0) > 0]
        losses = [e for e in closed if (e.pnl_pct or 0) <= 0]

        plan_trades = [e for e in closed if e.plan_followed is not None]
        followed = [e for e in plan_trades if e.plan_followed]
        deviated = [e for e in plan_trades if not e.plan_followed]

        return JournalStats(
            total_trades=n,
            win_rate=len(wins) / n,
            avg_pnl_pct=sum(e.pnl_pct or 0 for e in closed) / n,
            avg_pnl_when_plan_followed=_mean_pnl(followed) if followed else None,
            avg_pnl_when_plan_deviated=_mean_pnl(deviated) if deviated else None,
            plan_follow_rate=len(followed) / len(plan_trades) if plan_trades else None,
            avg_emotional_state_before_wins=_mean_emotional(wins) if wins else None,
            avg_emotional_state_before_losses=_mean_emotional(losses) if losses else None,
            expectancy_usdt=sum(e.pnl_usdt or 0 for e in closed) / n,
        )

    # ----------------------------------------------------------------- private

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                raw = json.load(f)
            for oid, data in raw.items():
                self._entries[oid] = TradeEntry(**data)
        except Exception as exc:
            logger.warning("Journal: could not load %s: %s", self._path, exc)

    def _save(self) -> None:
        try:
            data = {oid: asdict(e) for oid, e in self._entries.items()}
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as exc:
            logger.warning("Journal: could not save %s: %s", self._path, exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mean_pnl(entries: list[TradeEntry]) -> float:
    vals = [e.pnl_pct or 0 for e in entries]
    return sum(vals) / len(vals) if vals else 0.0


def _mean_emotional(entries: list[TradeEntry]) -> float | None:
    vals = [e.emotional_state_before for e in entries if e.emotional_state_before is not None]
    return sum(vals) / len(vals) if vals else None
