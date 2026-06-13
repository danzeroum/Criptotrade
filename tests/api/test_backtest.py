"""Backtest job persistence tests (P2-1)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.api.schemas import BacktestConfigIn, BacktestResultOut
from src.core.db import connection, init_db


class _MockExchangeClient:
    async def fetch_ohlcv(self, pair, timeframe="1h", limit=500):
        ts = 1_700_000_000_000
        return [[ts + i * 3_600_000, 50_000.0, 51_000.0, 49_000.0, 50_500.0, 100.0] for i in range(limit)]


def _make_client(tmp_path, extra_overrides=None):
    app = create_app()
    app.dependency_overrides[deps.get_exchange_client] = lambda: _MockExchangeClient()
    if extra_overrides:
        app.dependency_overrides.update(extra_overrides)
    return TestClient(app)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    return tmp_path


def test_run_returns_202_with_running_status(db, monkeypatch):
    c = _make_client(db)
    r = c.post("/v1/backtest/run", json={})
    assert r.status_code == 202
    data = r.json()["data"]
    assert data["status"] == "running"
    assert data["job_id"].startswith("job_")


def test_get_unknown_job_returns_404(db):
    c = _make_client(db)
    r = c.get("/v1/backtest/jobs/job_unknown")
    assert r.status_code == 404
    assert r.json()["error"] == "job_not_found"


# ------------------------------------------------------------- per-symbol pair
def test_run_persists_requested_pair(db):
    c = _make_client(db)
    r = c.post("/v1/backtest/run", json={"pair": "ETH/USDT"})
    assert r.status_code == 202
    job_id = r.json()["data"]["job_id"]
    with connection() as conn:
        row = conn.execute(
            "SELECT config_json FROM backtest_jobs WHERE id=?", (job_id,)
        ).fetchone()
    assert '"pair":"ETH/USDT"' in row["config_json"]  # backtests the chosen pair


def test_run_normalizes_dash_pair(db):
    c = _make_client(db)
    r = c.post("/v1/backtest/run", json={"pair": "eth-usdt"})
    assert r.status_code == 202
    job_id = r.json()["data"]["job_id"]
    with connection() as conn:
        row = conn.execute(
            "SELECT config_json FROM backtest_jobs WHERE id=?", (job_id,)
        ).fetchone()
    assert '"pair":"ETH/USDT"' in row["config_json"]


def test_run_rejects_pair_outside_allowlist(db):
    c = _make_client(db)
    r = c.post("/v1/backtest/run", json={"pair": "FOO/BAR"})
    assert r.status_code == 422


def test_montecarlo_accepts_pair(db):
    c = _make_client(db)
    r = c.post("/v1/backtest/montecarlo", json={"pair": "SOL/USDT", "monte_carlo_sims": 100})
    assert r.status_code == 200
    assert r.json()["data"]["n"] >= 0


def test_job_persists_after_restart(db):
    """A done job is still readable by a fresh app instance (no shared _jobs dict)."""
    from src.api.routes.backtest import _insert_running, _mark_done

    job_id = "job_persist_test"
    _insert_running(job_id, BacktestConfigIn())

    result = BacktestResultOut(
        total_trades=5,
        win_rate=0.6,
        pnl_pct=5.0,
        pnl_usdt=500.0,
        max_drawdown=2.0,
        sharpe=1.2,
        profit_factor=1.5,
        avg_win_pct=2.0,
        avg_loss_pct=1.0,
        expectancy=0.8,
        equity=[],
    )
    _mark_done(job_id, result)

    # Fresh app instance — zero shared in-memory state
    c2 = _make_client(db)
    r = c2.get(f"/v1/backtest/jobs/{job_id}")
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["status"] == "done"
    assert body["result"]["total_trades"] == 5
    assert body["result"]["win_rate"] == pytest.approx(0.6)


def test_reconcile_marks_orphan_running_as_error(db):
    """Jobs still 'running' at startup are flipped to 'error'."""
    from src.api.routes.backtest import _insert_running, _reconcile_orphans

    job_id = "job_orphan"
    _insert_running(job_id, BacktestConfigIn())

    with connection() as conn:
        row = conn.execute("SELECT status FROM backtest_jobs WHERE id=?", (job_id,)).fetchone()
    assert row["status"] == "running"

    _reconcile_orphans()

    with connection() as conn:
        row = conn.execute("SELECT * FROM backtest_jobs WHERE id=?", (job_id,)).fetchone()
    assert row["status"] == "error"
    assert "interrupted" in row["error"]


def test_mark_error_stores_message(db):
    from src.api.routes.backtest import _insert_running, _mark_error

    job_id = "job_err"
    _insert_running(job_id, BacktestConfigIn())
    _mark_error(job_id, "exchange timeout")

    with connection() as conn:
        row = conn.execute("SELECT * FROM backtest_jobs WHERE id=?", (job_id,)).fetchone()
    assert row["status"] == "error"
    assert row["error"] == "exchange timeout"
