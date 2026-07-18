"""A6 dispatcher: tails alerts.jsonl and delivers through the channels.

Why tail the JSONL (not the AlertBus, not the orchestrator): the append-only
``alerts.jsonl`` on the shared LEDGER_DIR volume is the ONLY meeting point of
the two processes — the orchestrator writes circuit-breaker alerts there and
never touches the API's in-process bus, while the API writes guardrail alerts
and outlives orchestrator restarts.

Duplicate-delivery hardening (approved design): the byte-offset cursor is
advanced with an OPTIMISTIC update (``WHERE pos = expected``) BEFORE any
delivery, so if the API ever runs with N workers, exactly one dispatcher wins
each batch and the others skip — at-most-once semantics (a crash mid-batch
drops, never duplicates; a duplicate Telegram on a critical alert erodes trust
faster than a rare miss).

Pipeline per alert: rules (type × min severity) → quiet hours (low/medium
suppressed inside the window — the console/drawer keeps EVERY alert; only the
external delivery is silenced) → anti-flood grouping per (channel, type, pair)
→ send with retry/backoff → ``notification_sent``/``notification_failed`` in
the ledger (surfaced by the A4 trail as action ``notification``).
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from src.core.ledger import TradingLedger
from src.notifications.senders import send_via_channel
from src.notifications.store import SEVERITY_ORDER, NotificationStore

logger = logging.getLogger(__name__)

# Retry backoff (seconds) between attempts; tests shrink this to [0, 0].
BACKOFF_S: List[float] = [2.0, 4.0]

_SEV_TAG = {"low": "LOW", "medium": "MED", "high": "HIGH", "critical": "CRIT"}


def _alerts_path() -> Path:
    return Path(os.getenv("LEDGER_DIR", ".buildtovalue/ledger")) / "alerts.jsonl"


def _in_quiet_hours(settings: Dict[str, Any], now: datetime) -> bool:
    start, end = settings.get("quiet_start"), settings.get("quiet_end")
    if not start or not end:
        return False
    try:
        tz = ZoneInfo(settings.get("quiet_tz") or "America/Sao_Paulo")
    except Exception:
        tz = timezone.utc
    t = now.astimezone(tz).strftime("%H:%M")
    if start <= end:
        return start <= t < end
    return t >= start or t < end  # window crossing midnight


class Dispatcher:
    def __init__(self, store: Optional[NotificationStore] = None,
                 ledger: Optional[TradingLedger] = None) -> None:
        self.store = store or NotificationStore()
        self.ledger = ledger or TradingLedger()
        # Anti-flood window state: (channel_id, type, pair) -> {last, suppressed}.
        # In-memory by design (declared): an API restart resets the counters,
        # which only means one extra delivery — acceptable for flood control.
        self._groups: Dict[tuple, Dict[str, Any]] = {}

    def ensure_initialized(self) -> None:
        """First boot ever: start the cursor at the END of alerts.jsonl so a
        fresh deploy doesn't blast months of historical alerts through the
        channels. Later boots keep the persisted cursor (no re-delivery)."""
        if not self.store.has_cursor():
            path = _alerts_path()
            self.store.reset_cursor(path.stat().st_size if path.exists() else 0)

    # ------------------------------------------------------------------ intake
    def dispatch_pending(self, now: Optional[datetime] = None) -> int:
        """Read new alerts past the cursor and deliver them. Returns how many
        alerts were processed (0 when nothing new or another worker won)."""
        now = now or datetime.now(timezone.utc)
        path = _alerts_path()
        size = path.stat().st_size if path.exists() else 0
        pos = self.store.get_cursor()
        if size < pos:
            # File shrank/rotated: skip history, restart from the end.
            self.store.reset_cursor(size)
            return 0
        if size == pos:
            return 0
        with path.open("rb") as handle:
            handle.seek(pos)
            chunk = handle.read(size - pos)
        # Only consume COMPLETE lines; a partially-written last line stays for
        # the next pass.
        last_nl = chunk.rfind(b"\n")
        if last_nl < 0:
            return 0
        chunk = chunk[: last_nl + 1]
        new_pos = pos + len(chunk)
        # Optimistic claim BEFORE delivering (single-dispatcher guarantee).
        if not self.store.advance_cursor(pos, new_pos):
            return 0
        processed = 0
        for line in chunk.decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                alert = json.loads(line)
            except ValueError:
                continue
            self._route(alert, now)
            processed += 1
        return processed

    # ----------------------------------------------------------------- routing
    def _route(self, alert: Dict[str, Any], now: datetime) -> None:
        severity = alert.get("severity", "low")
        alert_type = alert.get("type", "unknown")
        rules = [r for r in self.store.list_rules() if r["enabled"]]
        channel_ids: List[str] = []
        for rule in rules:
            if rule["alert_type"] not in ("*", alert_type):
                continue
            if SEVERITY_ORDER.get(severity, 0) < SEVERITY_ORDER.get(rule["min_severity"], 2):
                continue
            channel_ids.extend(c for c in rule["channel_ids"] if c not in channel_ids)
        if not channel_ids:
            return

        settings = self.store.get_settings()
        if _in_quiet_hours(settings, now) and severity in ("low", "medium"):
            # Quiet hours silence the EXTERNAL delivery only — the alert stays
            # in the console/drawer untouched.
            logger.info("Quiet hours: suppressing %s alert %s", severity, alert.get("id"))
            return

        window = timedelta(minutes=int(settings.get("group_window_min") or 5))
        for channel_id in channel_ids:
            channel = self.store.get_channel(channel_id)
            if channel is None or not channel["enabled"]:
                continue
            key = (channel_id, alert_type, alert.get("pair"))
            group = self._groups.get(key)
            if group and (now - group["last"]) < window:
                group["suppressed"] += 1
                continue
            suffix = ""
            if group and group["suppressed"]:
                suffix = f" (+{group['suppressed']} suprimidos na janela anterior)"
            self._groups[key] = {"last": now, "suppressed": 0}
            self._deliver(channel, alert, suffix)

    # ---------------------------------------------------------------- delivery
    def _deliver(self, channel: Dict[str, Any], alert: Dict[str, Any], suffix: str) -> None:
        severity = alert.get("severity", "low")
        subject = f"[{_SEV_TAG.get(severity, '?')}] Criptotrade · {alert.get('type', 'alerta')}"
        pair = f" ({alert['pair']})" if alert.get("pair") else ""
        text = f"{alert.get('message', '')}{pair}{suffix}"
        config = self.store.channel_config(channel)
        payload = {"alert": alert, "channel": channel["label"]}

        base = {
            "actor": "notifier",
            "channel_id": channel["id"],
            "channel_kind": channel["kind"],
            "channel_label": channel["label"],
            "alert_id": alert.get("id"),
            "alert_type": alert.get("type"),
            "severity": severity,
            "symbol": alert.get("pair"),
        }
        attempts = len(BACKOFF_S) + 1
        for attempt in range(1, attempts + 1):
            try:
                send_via_channel(channel["kind"], config, subject, text, payload)
                self.ledger.log_decision(
                    "notification_sent", {**base, "attempt": attempt, "success": True}
                )
                return
            except Exception as exc:  # noqa: BLE001 - sender errors end in the ledger
                logger.warning("Notification via %s failed (attempt %d/%d): %s",
                               channel["kind"], attempt, attempts, exc)
                if attempt <= len(BACKOFF_S):
                    time.sleep(BACKOFF_S[attempt - 1])
                else:
                    self.ledger.log_decision("notification_failed", {
                        **base, "attempts": attempts, "error": str(exc)[:300],
                        "success": False,
                    })


__all__ = ["Dispatcher", "BACKOFF_S"]
