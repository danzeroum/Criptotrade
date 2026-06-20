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
