"""Unit tests for the alert store (persistence) and bus (live fan-out)."""
from __future__ import annotations

import asyncio

import pytest

from src.core.alerts import Alert, AlertBus, AlertStore, publish_alert


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
