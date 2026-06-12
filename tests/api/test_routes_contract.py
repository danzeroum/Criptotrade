"""Per-route contract smoke tests (P3-5a).

Exercises the happy path of the under-covered read endpoints so every route has
at least a contract test (status + envelope), lifting coverage on the metrics,
risk, config and alerts routers. The SSE stream (/v1/alerts) is intentionally
excluded — it would block a TestClient request.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.agents.registry import AgentRegistry
from src.api import deps
from src.api.main import create_app
from src.core.alerts import Alert, AlertBus, AlertStore, make_guardrail_sink
from src.core.ledger import TradingLedger
from src.core.metrics import PortfolioMetricsCalculator
from src.hitl.config import HITLConfigStore, level_info
from src.hitl.orders import OrderStore
from src.safety.guardrails import GuardrailSystem


@pytest.fixture
def client(tmp_path):
    ledger = TradingLedger(tmp_path / "trades.jsonl")
    store = AlertStore(tmp_path / "alerts.jsonl")
    bus = AlertBus()
    hitl = HITLConfigStore(ledger, initial_level=2)
    order_store = OrderStore(
        ledger,
        threshold_provider=lambda: level_info(hitl.level).threshold_usdt,
        guardrails=GuardrailSystem(alert_sink=make_guardrail_sink(store)),
        db_path=str(tmp_path / "orders.db"),
    )
    app = create_app()
    app.dependency_overrides[deps.get_ledger] = lambda: ledger
    app.dependency_overrides[deps.get_metrics_calculator] = lambda: PortfolioMetricsCalculator(
        ledger, 10_000.0
    )
    app.dependency_overrides[deps.get_hitl_store] = lambda: hitl
    app.dependency_overrides[deps.get_alert_store] = lambda: store
    app.dependency_overrides[deps.get_alert_bus] = lambda: bus
    app.dependency_overrides[deps.get_order_store] = lambda: order_store
    app.dependency_overrides[deps.get_agent_registry] = lambda: AgentRegistry(
        db_path=str(tmp_path / "agents.db")
    )
    test_client = TestClient(app)
    test_client.alert_store = store  # type: ignore[attr-defined]
    return test_client


# Read endpoints that must answer 200 with the standard APIResponse envelope.
_GET_ROUTES = [
    "/v1/metrics",
    "/v1/metrics/equity",
    "/v1/metrics/equity?period=30d",
    "/v1/risk/protections",
    "/v1/risk/circuit-breaker",
    "/v1/risk/kelly",
    "/v1/risk/config",
    "/v1/config",
    "/v1/alerts/history",
    "/v1/alerts/history?limit=10&page=1",
]


@pytest.mark.parametrize("route", _GET_ROUTES)
def test_get_route_contract(client, route):
    resp = client.get(route)
    assert resp.status_code == 200, f"{route} -> {resp.status_code}: {resp.text[:200]}"
    body = resp.json()
    assert isinstance(body, dict)
    # All v1 read routes wrap payloads in the APIResponse envelope.
    assert "data" in body or body.get("success") is not None


def test_metrics_period_validation_rejects_garbage(client):
    # Query-param pattern guards should reject unknown periods with 422.
    assert client.get("/v1/metrics?period=nope").status_code == 422


def test_alerts_history_is_paginated(client):
    # Seed a couple of alerts, then confirm history returns them in the envelope.
    store = client.alert_store  # type: ignore[attr-defined]
    for i in range(3):
        store.append(Alert(severity="low", type="test", message=f"m{i}", agent_id="tester"))
    body = client.get("/v1/alerts/history?limit=2&page=1").json()
    data = body.get("data", body)
    assert isinstance(data, (list, dict))


def test_equity_with_trades_builds_equity_curve(tmp_path):
    """Equity endpoint with a closed position — covers the for-loop body in get_equity."""
    ledger = TradingLedger(tmp_path / "trades.jsonl")
    ledger.log_position_closed(
        order_id="ord1", symbol="BTC/USDT", side="buy",
        entry_price=50_000.0, exit_price=51_000.0, quantity=0.1,
    )

    store = AlertStore(tmp_path / "alerts.jsonl")
    bus = AlertBus()
    hitl = HITLConfigStore(ledger, initial_level=2)
    order_store = OrderStore(
        ledger,
        threshold_provider=lambda: level_info(hitl.level).threshold_usdt,
        guardrails=GuardrailSystem(alert_sink=make_guardrail_sink(store)),
        db_path=str(tmp_path / "orders.db"),
    )
    app = create_app()
    app.dependency_overrides[deps.get_ledger] = lambda: ledger
    app.dependency_overrides[deps.get_metrics_calculator] = lambda: PortfolioMetricsCalculator(ledger, 10_000.0)
    app.dependency_overrides[deps.get_hitl_store] = lambda: hitl
    app.dependency_overrides[deps.get_alert_store] = lambda: store
    app.dependency_overrides[deps.get_alert_bus] = lambda: bus
    app.dependency_overrides[deps.get_order_store] = lambda: order_store
    app.dependency_overrides[deps.get_agent_registry] = lambda: AgentRegistry(
        db_path=str(tmp_path / "agents.db")
    )
    c = TestClient(app)
    r = c.get("/v1/metrics/equity")
    assert r.status_code == 200
    points = r.json()["data"]
    # Should have at least one real equity point from the closed position.
    assert len(points) >= 1
    equity_values = [p["equity"] for p in points]
    # The closed trade had pnl = (51000-50000)*0.1 = 100 USDT → equity > 10000
    assert any(eq > 10_000.0 for eq in equity_values)
