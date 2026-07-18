"""Prometheus /metrics, readiness probe, and liveness (v2 observability)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_metrics_endpoint_exposes_prometheus_format():
    client = _client()
    client.get("/health")  # generate at least one counted request
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text
    assert "http_request_duration_seconds" in r.text
    assert "# HELP" in r.text


def test_readiness_probe_reports_ready():
    r = _client().get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["checks"]["db"] == "ok"


def test_liveness_probe():
    r = _client().get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_metrics_is_public_no_auth(monkeypatch):
    # Even with API keys configured, infra probes stay public.
    monkeypatch.setenv("API_KEYS", "secret-key")
    client = _client()
    assert client.get("/metrics").status_code == 200
    assert client.get("/health/ready").status_code == 200


def test_domain_collector_emits_gauges_from_ledger(tmp_path):
    from src.api.observability import DomainMetricsCollector
    from src.core.ledger import TradingLedger

    led = TradingLedger(tmp_path / "trades.jsonl")
    led.log_position_closed("o1", "BTC/USDT", "buy", 100.0, 110.0, 1.0)  # +10
    collector = DomainMetricsCollector(ledger_factory=lambda: led)

    families = {f.name: f for f in collector.collect()}
    assert "criptotrade_total_trades" in families
    assert families["criptotrade_total_trades"].samples[0].value == 1.0


def test_metrics_endpoint_includes_domain_gauges():
    text = _client().get("/metrics").text
    assert "criptotrade_open_positions" in text


def _open_positions_value(collector) -> float:
    """Read the criptotrade_open_positions gauge without depending on order."""
    families = {f.name: f for f in collector.collect()}
    family = families["criptotrade_open_positions"]
    sample = next(s for s in family.samples if s.name == "criptotrade_open_positions")
    return sample.value


def test_open_positions_gauge_reads_operational_store(tmp_path):
    # A bare order_fill (no matching position_closed) is exactly the historical
    # data that made the ledger-replay count balloon (e.g. 18,326). The gauge must
    # reflect the operational open_positions table, not the fill replay.
    from src.api.observability import DomainMetricsCollector
    from src.core.ledger import TradingLedger
    from src.orchestration.position_store import PositionStore

    led = TradingLedger(tmp_path / "trades.jsonl")
    led.log_fill("o1", "BTC/USDT", "buy", 100.0, 1.0)  # fill with no close
    collector = DomainMetricsCollector(ledger_factory=lambda: led)

    # Operational store is empty -> gauge is 0, despite the open fill in the ledger.
    assert _open_positions_value(collector) == 0.0

    # Seed the SAME db the collector reads (shared db_path is the regression point).
    PositionStore(lambda: led.db_path).upsert(
        "o1",
        {
            "symbol": "BTC/USDT", "side": "buy", "entry_price": 100.0, "quantity": 1.0,
            "stop_loss": None, "take_profit": None, "opened_at": "2026-01-01T00:00:00+00:00",
        },
    )
    assert _open_positions_value(collector) == 1.0
