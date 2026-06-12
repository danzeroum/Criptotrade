"""Tests for /v1/config, /v1/agents/{id}/config, /v1/alerts/config."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.routes import config as config_mod


@pytest.fixture(autouse=True)
def _reset_overrides():
    """Ensure runtime overrides are clean before and after each test."""
    config_mod._runtime_overrides.clear()
    yield
    config_mod._runtime_overrides.clear()


@pytest.fixture
def client():
    return TestClient(create_app())


# ── GET /v1/config ────────────────────────────────────────────────────────────

def test_get_config_defaults(client):
    r = client.get("/v1/config")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["dry_run"] is True
    assert d["initial_capital"] == pytest.approx(10_000.0)
    assert d["orchestrator_interval_seconds"] == 60
    assert d["app_env"] == "development"
    assert "exchange" in d


def test_get_config_env_override(client, monkeypatch):
    monkeypatch.setenv("INITIAL_CAPITAL", "25000")
    monkeypatch.setenv("ORCHESTRATOR_INTERVAL_SECONDS", "30")
    r = client.get("/v1/config")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["initial_capital"] == pytest.approx(25_000.0)
    assert d["orchestrator_interval_seconds"] == 30


# ── PATCH /v1/config ──────────────────────────────────────────────────────────

def test_patch_config_initial_capital(client):
    r = client.patch("/v1/config", json={"initial_capital": 50_000.0})
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["initial_capital"] == pytest.approx(50_000.0)


def test_patch_config_interval(client):
    r = client.patch("/v1/config", json={"orchestrator_interval_seconds": 120})
    assert r.status_code == 200
    assert r.json()["data"]["orchestrator_interval_seconds"] == 120


def test_patch_config_empty_body_is_noop(client):
    r = client.patch("/v1/config", json={})
    assert r.status_code == 200
    assert r.json()["data"]["initial_capital"] == pytest.approx(10_000.0)


def test_patch_config_persists_across_get(client):
    client.patch("/v1/config", json={"initial_capital": 99_999.0})
    r = client.get("/v1/config")
    assert r.json()["data"]["initial_capital"] == pytest.approx(99_999.0)


# ── PATCH /v1/agents/{id}/config ──────────────────────────────────────────────

def test_patch_agent_config_known_agent(client):
    r = client.patch("/v1/agents/strategy/config", json={"confidence_threshold": 0.75})
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["id"] == "strategy"
    assert "confidence_threshold" in d["params"]
    assert d["params"]["confidence_threshold"] == pytest.approx(0.75)


def test_patch_agent_config_unknown_agent(client):
    r = client.patch("/v1/agents/nonexistent/config", json={"foo": "bar"})
    assert r.status_code == 404
    assert r.json()["error"] == "agent_not_found"


# ── PATCH /v1/alerts/config ───────────────────────────────────────────────────

def test_patch_alerts_config(client):
    r = client.patch("/v1/alerts/config", json={"risk_of_ruin_alert_pct": 3.0})
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["risk_of_ruin_alert_pct"] == pytest.approx(3.0)
    assert "revenge_size_multiplier" in d


def test_patch_alerts_config_partial(client):
    r = client.patch("/v1/alerts/config", json={"euphoria_size_multiplier": 1.10})
    assert r.status_code == 200
    assert r.json()["data"]["euphoria_size_multiplier"] == pytest.approx(1.10)


def test_get_config_bool_env_override(client, monkeypatch):
    monkeypatch.setenv("EXCHANGE_DRY_RUN", "false")
    r = client.get("/v1/config")
    assert r.json()["data"]["dry_run"] is False


def test_get_config_invalid_env_falls_back_to_default(client, monkeypatch):
    monkeypatch.setenv("INITIAL_CAPITAL", "not-a-number")
    r = client.get("/v1/config")
    assert r.json()["data"]["initial_capital"] == pytest.approx(10_000.0)
