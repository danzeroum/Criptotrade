"""Tests for /v1/alerts — paginated history and SSE stream."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.core.alerts import Alert, AlertBus, AlertStore


@pytest.fixture
def store(tmp_path):
    return AlertStore(tmp_path / "alerts.jsonl")


@pytest.fixture
def bus():
    return AlertBus()


@pytest.fixture
def client(store, bus):
    app = create_app()
    app.dependency_overrides[deps.get_alert_store] = lambda: store
    app.dependency_overrides[deps.get_alert_bus] = lambda: bus
    return TestClient(app)


def _alert(**kwargs):
    defaults = dict(severity="high", type="test_event", message="test alert")
    defaults.update(kwargs)
    return Alert(**defaults)


# ── GET /v1/alerts/history ───────────────────────────────────────────────────

def test_history_empty(client):
    r = client.get("/v1/alerts/history")
    assert r.status_code == 200
    body = r.json()
    assert body["data"] == []
    assert body["meta"]["total"] == 0


def test_history_returns_all_alerts(client, store):
    store.append(_alert(message="alert A"))
    store.append(_alert(message="alert B"))
    r = client.get("/v1/alerts/history")
    assert r.status_code == 200
    assert r.json()["meta"]["total"] == 2


def test_history_newest_first_ordering(client, store):
    store.append(_alert(message="first"))
    store.append(_alert(message="second"))
    data = client.get("/v1/alerts/history").json()["data"]
    assert data[0]["message"] == "second"
    assert data[1]["message"] == "first"


def test_history_response_shape(client, store):
    store.append(_alert(severity="critical", type="guardrail", message="pos size exceeded"))
    data = client.get("/v1/alerts/history").json()["data"]
    alert = data[0]
    for key in ("id", "severity", "type", "message", "occurred_at"):
        assert key in alert
    assert alert["severity"] == "critical"
    assert alert["type"] == "guardrail"


def test_history_severity_filter(client, store):
    store.append(_alert(severity="high"))
    store.append(_alert(severity="low"))
    store.append(_alert(severity="critical"))
    r = client.get("/v1/alerts/history?severity=high")
    body = r.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["severity"] == "high"


def test_history_invalid_severity_returns_422(client):
    assert client.get("/v1/alerts/history?severity=unknown").status_code == 422


def test_history_all_severity_levels(client, store):
    for sev in ("low", "medium", "high", "critical"):
        store.append(_alert(severity=sev))
    for sev in ("low", "medium", "high", "critical"):
        r = client.get(f"/v1/alerts/history?severity={sev}")
        assert r.status_code == 200
        assert r.json()["meta"]["total"] == 1


def test_history_pagination_limit(client, store):
    for i in range(5):
        store.append(_alert(message=f"alert {i}"))
    body = client.get("/v1/alerts/history?limit=2&page=1").json()
    assert body["meta"]["total"] == 5
    assert len(body["data"]) == 2
    assert body["meta"]["per_page"] == 2


def test_history_pagination_page_two(client, store):
    for i in range(4):
        store.append(_alert(message=f"alert {i}"))
    body = client.get("/v1/alerts/history?limit=2&page=2").json()
    assert len(body["data"]) == 2


def test_history_optional_fields_present(client, store):
    store.append(_alert(severity="medium", type="risk", message="RR below threshold",
                        agent_id="risk_agent", pair="BTC/USDT", auto_action="cancel"))
    data = client.get("/v1/alerts/history").json()["data"]
    assert data[0]["agent_id"] == "risk_agent"
    assert data[0]["pair"] == "BTC/USDT"
    assert data[0]["auto_action"] == "cancel"


# ── GET /v1/alerts (SSE) ─────────────────────────────────────────────────────
# NOTE: The live SSE stream is intentionally not tested end-to-end here —
# EventSourceResponse blocks a synchronous TestClient until the stream closes,
# which never happens for the live feed. See test_routes_contract.py for context.
# We cover: FastAPI query-param validation (422) and the _json helper.

def test_sse_invalid_severity_returns_422(client):
    # FastAPI validates the regex pattern before entering the SSE handler, so
    # no streaming is initiated and the response arrives synchronously.
    r = client.get("/v1/alerts?severity=bad")
    assert r.status_code == 422


# ── _json helper ─────────────────────────────────────────────────────────────

def test_json_helper_serializes_dict():
    from src.api.routes.alerts import _json
    payload = {"id": "alert_abc123", "severity": "high", "message": "test"}
    result = _json(payload)
    assert "alert_abc123" in result
    assert "high" in result


def test_json_helper_preserves_unicode():
    from src.api.routes.alerts import _json
    result = _json({"msg": "Violação de guardrail: tamanho excede 5%"})
    assert "Violação" in result
    assert "tamanho" in result
