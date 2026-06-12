"""Tests for /v1/journal — CRUD and metrics."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.core.db import init_db


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    return tmp_path


@pytest.fixture
def client(db):
    return TestClient(create_app())


def _entry(**kwargs):
    defaults = dict(
        setup="BTC breakout test",
        emotion_before=5,
        emotion_after=7,
        stop_defined=True,
        plan_followed=True,
        pnl_pct=1.5,
        note="Went well",
    )
    defaults.update(kwargs)
    return defaults


# ── GET /v1/journal ───────────────────────────────────────────────────────────

def test_list_empty(client):
    r = client.get("/v1/journal")
    assert r.status_code == 200
    body = r.json()
    assert body["data"] == []
    assert body["meta"]["total"] == 0


def test_list_after_create(client):
    client.post("/v1/journal", json=_entry())
    r = client.get("/v1/journal")
    assert r.status_code == 200
    assert len(r.json()["data"]) == 1


def test_list_pagination(client):
    for i in range(5):
        client.post("/v1/journal", json=_entry(setup=f"Trade {i}"))
    r = client.get("/v1/journal?limit=2&offset=0")
    body = r.json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] == 5
    assert body["meta"]["per_page"] == 2


# ── POST /v1/journal ──────────────────────────────────────────────────────────

def test_create_returns_201(client):
    r = client.post("/v1/journal", json=_entry())
    assert r.status_code == 201
    d = r.json()["data"]
    assert d["setup"] == "BTC breakout test"
    assert d["pnl_pct"] == pytest.approx(1.5)
    assert "id" in d
    assert "created_at" in d


def test_create_minimal_required_fields(client):
    payload = dict(
        setup="Quick scalp",
        emotion_before=3,
        stop_defined=False,
        plan_followed=False,
    )
    r = client.post("/v1/journal", json=payload)
    assert r.status_code == 201
    d = r.json()["data"]
    assert d["pnl_pct"] is None
    assert d["note"] is None
    assert d["emotion_after"] is None


def test_create_validation_error(client):
    payload = dict(setup="X", emotion_before=11, stop_defined=True, plan_followed=True)
    r = client.post("/v1/journal", json=payload)
    assert r.status_code == 422


# ── GET /v1/journal/metrics ───────────────────────────────────────────────────

def test_metrics_empty(client):
    r = client.get("/v1/journal/metrics")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["by_emotion"] == []
    assert d["plan_followed_pnl"] is None
    assert d["real_win_rate"] is None
    assert d["discipline_correlation"] is None


def test_metrics_with_entries(client):
    for pnl, plan in [(2.0, True), (-1.0, False), (1.5, True), (0.5, True)]:
        client.post("/v1/journal", json=_entry(pnl_pct=pnl, plan_followed=plan))

    r = client.get("/v1/journal/metrics")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["real_win_rate"] == pytest.approx(0.75)
    assert d["plan_followed_pnl"] is not None
    assert d["plan_deviated_pnl"] is not None


def test_metrics_discipline_correlation_with_sufficient_data(client):
    data = [
        (2.0, True), (1.5, True), (-1.0, False), (-0.5, False),
        (3.0, True), (-2.0, False),
    ]
    for pnl, plan in data:
        client.post("/v1/journal", json=_entry(pnl_pct=pnl, plan_followed=plan))

    r = client.get("/v1/journal/metrics")
    d = r.json()["data"]
    assert d["discipline_correlation"] is not None
    assert -1.0 <= d["discipline_correlation"] <= 1.0


def test_metrics_by_emotion_bands(client):
    # 3 entries in band 1–3 (emotion_before=2)
    for _ in range(3):
        client.post("/v1/journal", json=_entry(emotion_before=2, pnl_pct=1.0))

    r = client.get("/v1/journal/metrics")
    d = r.json()["data"]
    band_1_3 = next((b for b in d["by_emotion"] if b["band"] == "1–3"), None)
    assert band_1_3 is not None
    assert band_1_3["trades"] == 3
    assert band_1_3["win_rate"] == pytest.approx(1.0)
