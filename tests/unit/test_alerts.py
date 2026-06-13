"""Unit tests for the alert store (persistence) and bus (live fan-out)."""
from __future__ import annotations

import asyncio

import pytest

from src.core.alerts import Alert, AlertBus, AlertStore, make_guardrail_sink, publish_alert
from src.safety.guardrails import GuardrailSystem


@pytest.fixture
def store(tmp_path) -> AlertStore:
    return AlertStore(tmp_path / "alerts.jsonl")


def test_alert_rejects_bad_severity():
    with pytest.raises(ValueError):
        Alert(severity="urgent", type="t", message="m")


def test_store_history_empty(store):
    rows, total = store.history()
    assert rows == [] and total == 0


def test_store_history_newest_first(store):
    store.append(Alert(severity="low", type="t", message="first"))
    store.append(Alert(severity="high", type="t", message="second"))
    rows, total = store.history()
    assert total == 2
    assert rows[0]["message"] == "second"  # newest first


def test_store_history_severity_filter_and_pagination(store):
    for i in range(5):
        store.append(Alert(severity="critical", type="t", message=f"c{i}"))
        store.append(Alert(severity="low", type="t", message=f"l{i}"))
    rows, total = store.history(severity="critical", limit=2, offset=0)
    assert total == 5
    assert len(rows) == 2
    assert all(r["severity"] == "critical" for r in rows)


@pytest.mark.asyncio
async def test_bus_delivers_to_subscriber():
    bus = AlertBus()
    queue = bus.register()
    assert bus.subscriber_count == 1
    await bus.publish(Alert(severity="high", type="risk_rejection", message="boom"))
    payload = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert payload["type"] == "risk_rejection"
    bus.unregister(queue)
    assert bus.subscriber_count == 0


@pytest.mark.asyncio
async def test_publish_alert_persists_and_broadcasts(store):
    bus = AlertBus()
    queue = bus.register()
    await publish_alert(Alert(severity="medium", type="vol", message="x"), store, bus)
    # Persisted...
    rows, total = store.history()
    assert total == 1
    # ...and broadcast.
    payload = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert payload["type"] == "vol"


def test_guardrail_sink_publishes_violation(store):
    sink = make_guardrail_sink(store)
    # Missing stop_loss -> a violation that should reach the sink.
    gs = GuardrailSystem(alert_sink=sink)
    ok, violations = gs.validate_order({"position_size_pct": 2.0, "action": "BUY"})
    assert ok is False and violations
    rows, total = store.history(severity="high")
    assert total >= 1
    assert rows[0]["type"] == "guardrail_violation"


def test_guardrail_sink_failure_does_not_break_validation(store):
    def _boom(_msg: str) -> None:
        raise RuntimeError("sink down")

    gs = GuardrailSystem(alert_sink=_boom)
    # Validation must still return its verdict even if the sink raises.
    ok, violations = gs.validate_order({"position_size_pct": 99.0})
    assert ok is False and violations


def test_store_history_since_filter(tmp_path):
    """History with a `since` cutoff — covers AlertStore.history lines 84-87."""
    import json
    from datetime import datetime, timezone

    path = tmp_path / "alerts_since.jsonl"
    old_alert = Alert(severity="high", type="test", message="old").to_dict()
    new_alert = Alert(severity="high", type="test", message="new").to_dict()
    old_alert["occurred_at"] = "2020-06-01T00:00:00+00:00"
    new_alert["occurred_at"] = "2026-06-01T00:00:00+00:00"

    with path.open("w") as f:
        f.write(json.dumps(old_alert) + "\n")
        f.write(json.dumps(new_alert) + "\n")

    store = AlertStore(path)
    since = datetime(2021, 1, 1, tzinfo=timezone.utc)
    rows, total = store.history(since=since)
    assert total == 1
    assert rows[0]["message"] == "new"


def test_store_history_skips_blank_lines(tmp_path):
    """Blank lines in the JSONL file are skipped gracefully (line 80 branch)."""
    import json
    path = tmp_path / "alerts.jsonl"
    alert = Alert(severity="low", type="t", message="valid")
    with path.open("w") as f:
        f.write("\n")                                         # blank line
        f.write(json.dumps(alert.to_dict()) + "\n")           # real entry
        f.write("   \n")                                      # whitespace-only line

    store = AlertStore(path)
    rows, total = store.history()
    assert total == 1
    assert rows[0]["message"] == "valid"


def test_parse_ts_invalid_string_returns_none():
    from src.core.alerts import _parse_ts
    assert _parse_ts("not-a-date") is None
    assert _parse_ts("") is None
    assert _parse_ts(None) is None
