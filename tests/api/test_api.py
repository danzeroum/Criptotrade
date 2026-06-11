"""API tests for the Phase 1 surface (/v1/metrics, /v1/hitl, /v1/alerts)."""
from __future__ import annotations

import json
from datetime import UTC, datetime

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
    hitl.pending_orders_provider = order_store.pending_count

    app = create_app()
    app.dependency_overrides[deps.get_ledger] = lambda: ledger
    app.dependency_overrides[deps.get_metrics_calculator] = lambda: PortfolioMetricsCalculator(
        ledger, 10_000.0
    )
    app.dependency_overrides[deps.get_hitl_store] = lambda: hitl
    app.dependency_overrides[deps.get_alert_store] = lambda: store
    app.dependency_overrides[deps.get_alert_bus] = lambda: bus
    app.dependency_overrides[deps.get_order_store] = lambda: order_store
    # Cross-process cycles via SQLite (Phase 5a-iii): record_cycle writes, the
    # route reads cycles_today from the same db.
    agent_registry = AgentRegistry(db_path=str(tmp_path / "agents.db"))
    app.dependency_overrides[deps.get_agent_registry] = lambda: agent_registry

    test_client = TestClient(app)
    test_client.ledger = ledger  # type: ignore[attr-defined]
    test_client.alert_store = store  # type: ignore[attr-defined]
    test_client.order_store = order_store  # type: ignore[attr-defined]
    test_client.hitl = hitl  # type: ignore[attr-defined]
    test_client.agent_registry = agent_registry  # type: ignore[attr-defined]
    return test_client


_VALID_ORDER = {
    "pair": "BTC/USDT",
    "side": "buy",
    "quantity": 0.05,
    "price": 1000.0,
    "strategy": "dca_v1",
    "agent_id": "strategy_agent",
    "confidence": 0.87,
    "reason": "RSI oversold detectado no schedule DCA",
    # Risk fields: stop 3% below entry, RR = (1080-1000)/(1000-970) = 2.67 (>= 2.5).
    "position_size_pct": 2.0,
    "stop_loss": 970.0,
    "take_profit": 1080.0,
}


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
    base = datetime(2026, 1, 1, tzinfo=UTC)
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


# ----------------------------------------------------------------- orders (Phase 2)
def test_create_order_below_threshold_returns_201(client):
    # Level 2 threshold = $1000; notional = 0.05 * 1000 = 50 -> auto-approve.
    r = client.post("/v1/orders", json=_VALID_ORDER)
    assert r.status_code == 201
    d = r.json()["data"]
    assert d["status"] == "filled"
    assert d["auto_approved"] is True


def test_create_order_above_threshold_returns_202_pending(client):
    order = {**_VALID_ORDER, "quantity": 2.0}  # notional 2000 > 1000
    r = client.post("/v1/orders", json=order)
    assert r.status_code == 202
    assert r.json()["data"]["status"] == "pending"


def test_create_order_invalid_pair_returns_422_envelope(client):
    r = client.post("/v1/orders", json={**_VALID_ORDER, "pair": "btcusdt"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "validation_error"
    assert body["field"] == "pair"


def test_create_order_short_reason_returns_422(client):
    r = client.post("/v1/orders", json={**_VALID_ORDER, "reason": "curto"})
    assert r.status_code == 422
    assert r.json()["field"] == "reason"


def test_patch_approve_pending_order_approves(client):
    # Model B / cross-process: manual approve -> 'approved' (the loop fills later).
    order = client.post("/v1/orders", json={**_VALID_ORDER, "quantity": 2.0}).json()["data"]
    r = client.patch(
        f"/v1/orders/{order['id']}/status",
        json={"decision": "approve", "operator": "daniel"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "approved"
    assert r.json()["data"]["operator_id"] == "daniel"


def test_patch_reject_without_note_returns_422(client):
    order = client.post("/v1/orders", json={**_VALID_ORDER, "quantity": 2.0}).json()["data"]
    r = client.patch(f"/v1/orders/{order['id']}/status", json={"decision": "reject"})
    assert r.status_code == 422
    assert r.json()["field"] == "operator_note"


def test_patch_reject_with_note_succeeds(client):
    order = client.post("/v1/orders", json={**_VALID_ORDER, "quantity": 2.0}).json()["data"]
    r = client.patch(
        f"/v1/orders/{order['id']}/status",
        json={"decision": "reject", "operator_note": "risco elevado"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "rejected"


def test_patch_already_filled_returns_409(client):
    order = client.post("/v1/orders", json=_VALID_ORDER).json()["data"]  # auto-filled
    r = client.patch(
        f"/v1/orders/{order['id']}/status",
        json={"decision": "reject", "operator_note": "tarde demais"},
    )
    assert r.status_code == 409
    assert r.json()["error"] == "order_not_pending"


def test_patch_unknown_order_returns_404(client):
    r = client.patch("/v1/orders/ord_missing/status", json={"decision": "approve"})
    assert r.status_code == 404
    assert r.json()["error"] == "order_not_found"


def test_list_orders_filters_pending(client):
    client.post("/v1/orders", json={**_VALID_ORDER, "quantity": 2.0})  # pending
    client.post("/v1/orders", json=_VALID_ORDER)  # auto-filled
    r = client.get("/v1/orders?status=pending")
    body = r.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["status"] == "pending"


def test_pending_orders_reflected_in_hitl_config(client):
    client.post("/v1/orders", json={**_VALID_ORDER, "quantity": 2.0})  # pending
    cfg = client.get("/v1/hitl/config").json()["data"]
    assert cfg["pending_orders_count"] == 1


def test_autonomy_level_zero_forces_pending(client):
    client.hitl.set_level(0, "modo manual total", operator="roberto")
    r = client.post("/v1/orders", json=_VALID_ORDER)  # tiny notional, but level 0
    assert r.status_code == 202
    assert r.json()["data"]["status"] == "pending"


# ----------------------------------------------------------------- risk gate (Phase 4a)
def test_order_rejected_by_guardrail_risk_reward(client):
    # take_profit too close -> RR below 2.5 -> rejected by guardrails, not approved.
    bad = {**_VALID_ORDER, "take_profit": 1010.0}  # RR = 10/30 = 0.33
    r = client.post("/v1/orders", json=bad)
    assert r.status_code == 422
    d = r.json()["data"]
    assert d["status"] == "rejected"
    assert "Risk-reward" in d["operator_note"]


def test_order_rejected_when_stop_loss_wrong_side(client):
    # BUY with stop ABOVE entry violates the stop-loss guardrail -> rejected.
    bad = {**_VALID_ORDER, "stop_loss": 1100.0}
    r = client.post("/v1/orders", json=bad)
    assert r.status_code == 422
    assert r.json()["data"]["status"] == "rejected"


def test_guardrail_rejection_publishes_alert(client):
    client.post("/v1/orders", json={**_VALID_ORDER, "take_profit": 1010.0})
    alerts = client.get("/v1/alerts/history").json()
    assert alerts["meta"]["total"] >= 1
    assert any(a["type"] == "guardrail_violation" for a in alerts["data"])


def test_risk_passing_order_still_auto_approves(client):
    r = client.post("/v1/orders", json=_VALID_ORDER)
    assert r.status_code == 201
    assert r.json()["data"]["status"] == "filled"


# ----------------------------------------------------------------- agents (Phase 3a)
def test_list_agents(client):
    r = client.get("/v1/agents")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 5
    ids = {a["id"] for a in data}
    assert {"strategy", "risk", "execution", "recovery", "exploration"} == ids


def test_agent_detail_implemented(client):
    r = client.get("/v1/agents/strategy")
    assert r.status_code == 200
    assert r.json()["data"]["implemented"] is True


def test_agent_stub_returns_501(client):
    for stub in ("recovery", "exploration"):
        r = client.get(f"/v1/agents/{stub}")
        assert r.status_code == 501
        assert r.json()["error"] == "not_implemented"


def test_agent_unknown_returns_404(client):
    r = client.get("/v1/agents/does_not_exist")
    assert r.status_code == 404
    assert r.json()["error"] == "agent_not_found"


def test_agent_cycles_served_from_db(client):
    # 5a-iii: the loop's record_cycle writes cycle_events; the API reads them.
    client.agent_registry.record_cycle("strategy")
    client.agent_registry.record_cycle("strategy")
    r = client.get("/v1/agents/strategy")
    body = r.json()["data"]
    assert body["cycles"] == 2
    assert body["last_action_at"] is not None


# ----------------------------------------------------------------- agents /config
def test_agent_config_implemented(client):
    r = client.get("/v1/agents/risk/config")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["implemented"] is True
    params = data["params"]
    assert params["max_position_size_pct"] == 5.0
    assert params["stop_loss_pct"] == 3.0
    assert params["max_daily_loss_pct"] == 5.0
    assert params["reasoning_pattern"] == "reflection"
    assert params["autonomy_level"] == 3


def test_agent_config_strategy_params(client):
    r = client.get("/v1/agents/strategy/config")
    assert r.status_code == 200
    params = r.json()["data"]["params"]
    assert params["confidence_threshold"] == 0.6
    assert "market_data" in params["tools"]
    assert params["reasoning_pattern"] == "chain_of_thought"


def test_agent_config_stub_returns_200_not_501(client):
    # /config always returns 200; stubs have empty params but are visible.
    for stub in ("recovery", "exploration"):
        r = client.get(f"/v1/agents/{stub}/config")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["implemented"] is False
        assert data["params"] == {}


def test_agent_config_unknown_returns_404(client):
    r = client.get("/v1/agents/does_not_exist/config")
    assert r.status_code == 404
    assert r.json()["error"] == "agent_not_found"


def test_agent_config_all_implemented_have_params(client):
    # Every implemented agent must expose at least one parameter.
    r = client.get("/v1/agents")
    assert r.status_code == 200
    for agent in r.json()["data"]:
        if not agent["implemented"]:
            continue
        cfg = client.get(f"/v1/agents/{agent['id']}/config")
        assert cfg.status_code == 200
        assert len(cfg.json()["data"]["params"]) > 0, (
            f"Agent '{agent['id']}' is implemented but has no params exposed"
        )


# ----------------------------------------------------------------- process log (Phase 3b)
def test_process_events_after_order(client):
    order = client.post("/v1/orders", json=_VALID_ORDER).json()["data"]  # auto-filled
    r = client.get(f"/v1/process/events?case_id={order['id']}")
    assert r.status_code == 200
    activities = [e["activity"] for e in r.json()["data"]]
    assert "order_submitted" in activities
    assert "order_filled" in activities


def test_process_events_empty(client):
    r = client.get("/v1/process/events")
    assert r.status_code == 200
    assert r.json()["data"] == []


# ----------------------------------------------------------------- risk/kelly (P1-4)
def test_kelly_empty_ledger_returns_insufficient(client):
    r = client.get("/v1/risk/kelly")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["data_quality"] == "insufficient"
    assert d["trades"] == 0
    assert d["full_kelly"] is None
    assert d["risk_of_ruin"] is None


def test_kelly_below_threshold_returns_insufficient(client):
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(9):
        _append_closed(client.ledger, 50.0 if i % 2 == 0 else -20.0, base, f"ord_{i}")
    r = client.get("/v1/risk/kelly")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["data_quality"] == "insufficient"
    assert d["trades"] == 9
    assert d["full_kelly"] is None


def test_kelly_sufficient_trades_returns_ok(client):
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(12):
        _append_closed(client.ledger, 100.0 if i % 2 == 0 else -30.0, base, f"ord_{i}")
    r = client.get("/v1/risk/kelly")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["data_quality"] == "ok"
    assert d["trades"] == 12
    assert d["full_kelly"] is not None
    assert d["risk_of_ruin"] is not None
    assert 0.0 <= d["risk_of_ruin"] <= 100.0


# ------------------------------------------------- catch-all exception → JSON 500 (P1-1)
def test_unhandled_exception_returns_json_500(client):
    from fastapi.testclient import TestClient

    from src.api import deps

    def broken():
        raise RuntimeError("simulated unhandled error")

    client.app.dependency_overrides[deps.get_ledger] = broken
    try:
        # raise_server_exceptions=False: ServerErrorMiddleware calls the
        # Exception handler and sends the response before re-raising; the
        # TestClient swallows the re-raise and returns what was sent.
        with TestClient(client.app, raise_server_exceptions=False) as tc:
            r = tc.get("/v1/risk/kelly")
    finally:
        del client.app.dependency_overrides[deps.get_ledger]

    assert r.status_code == 500
    body = r.json()
    assert body["error"] == "internal_error"
    assert "docs" in body


# ----------------------------------------- openapi at /v1/openapi.json (P1-6)
def test_openapi_schema_served_at_v1_path(client):
    r = client.get("/v1/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert schema["info"]["title"] == "Criptotrade API"
    assert "/v1/risk/kelly" in schema["paths"]
