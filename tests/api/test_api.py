"""API tests for the Phase 1 surface (/v1/metrics, /v1/hitl, /v1/alerts)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.core.alerts import Alert, AlertBus, AlertStore
from src.core.ledger import TradingLedger
from src.core.metrics import PortfolioMetricsCalculator
from src.hitl.config import HITLConfigStore


@pytest.fixture
def client(tmp_path):
    ledger = TradingLedger(tmp_path / "trades.jsonl")
    store = AlertStore(tmp_path / "alerts.jsonl")
    bus = AlertBus()
    hitl = HITLConfigStore(ledger, initial_level=2)

    app = create_app()
    app.dependency_overrides[deps.get_metrics_calculator] = lambda: PortfolioMetricsCalculator(
        ledger, 10_000.0
    )
    app.dependency_overrides[deps.get_hitl_store] = lambda: hitl
    app.dependency_overrides[deps.get_alert_store] = lambda: store
    app.dependency_overrides[deps.get_alert_bus] = lambda: bus

    test_client = TestClient(app)
    test_client.ledger = ledger  # type: ignore[attr-defined]
    test_client.alert_store = store  # type: ignore[attr-defined]
    return test_client


def _append_closed(ledger: TradingLedger, pnl: float, ts: datetime, order_id: str) -> None:
    entry = {"timestamp": ts.isoformat(), "event_type": "position_closed",
             "data": {"order_id": order_id, "pnl": pnl}}
    with ledger.ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


# ----------------------------------------------------------------- health
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


# ----------------------------------------------------------------- metrics
def test_metrics_empty_has_envelope(client):
    r = client.get("/v1/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "data" in body
    assert body["_links"]["self"].startswith("/v1/metrics")
    assert body["data"]["has_data"] is False
    assert body["data"]["sharpe_ratio"] is None


def test_metrics_with_trades(client):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _append_closed(client.ledger, 100.0, base, "a")
    _append_closed(client.ledger, -40.0, base, "b")
    r = client.get("/v1/metrics?period=all")
    d = r.json()["data"]
    assert d["total_trades"] == 2
    assert d["win_rate"] == pytest.approx(0.5)
    assert d["portfolio_value_usdt"] == 10_060.0


def test_metrics_invalid_period_returns_422_envelope(client):
    r = client.get("/v1/metrics?period=bogus")
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "validation_error"
    assert body["field"] == "period"


# ----------------------------------------------------------------- hitl
def test_hitl_config_levels(client):
    r = client.get("/v1/hitl/config")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["current_level"] == 2
    assert d["max_level"] == 3
    assert len(d["levels"]) == 4
    assert d["threshold_usdt"] == 1000.0


def test_hitl_patch_changes_level(client):
    r = client.patch("/v1/hitl/config", json={"level": 3, "reason": "subir autonomia"})
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["current_level"] == 3
    assert d["threshold_usdt"] == 5000.0
    assert d["last_changed_by"] == "operator"


def test_hitl_patch_invalid_level_422(client):
    r = client.patch("/v1/hitl/config", json={"level": 5, "reason": "demais"})
    assert r.status_code == 422
    assert r.json()["field"] == "level"


def test_hitl_patch_short_reason_422(client):
    r = client.patch("/v1/hitl/config", json={"level": 1, "reason": "x"})
    assert r.status_code == 422
    assert r.json()["field"] == "reason"


# ----------------------------------------------------------------- alerts
def test_alerts_history_empty(client):
    r = client.get("/v1/alerts/history")
    assert r.status_code == 200
    body = r.json()
    assert body["data"] == []
    assert body["meta"]["total"] == 0


def test_alerts_history_returns_appended(client):
    client.alert_store.append(Alert(severity="high", type="risk_rejection", message="boom"))
    r = client.get("/v1/alerts/history")
    body = r.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["severity"] == "high"
    assert body["data"][0]["type"] == "risk_rejection"


def test_alerts_history_severity_filter(client):
    client.alert_store.append(Alert(severity="low", type="t", message="a"))
    client.alert_store.append(Alert(severity="critical", type="t", message="b"))
    r = client.get("/v1/alerts/history?severity=critical")
    body = r.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["severity"] == "critical"
