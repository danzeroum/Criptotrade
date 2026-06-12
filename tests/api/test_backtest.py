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


def test_get_running_job_result_is_none(db):
    """GET a still-running job — covers the result_json=NULL branch in _get_job."""
    from src.api.routes.backtest import _insert_running

    job_id = "job_still_running"
    _insert_running(job_id, BacktestConfigIn())
    c = _make_client(db)
    r = c.get(f"/v1/backtest/jobs/{job_id}")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "running"
    assert data["result"] is None


# ── Synchronous endpoints ────────────────────────────────────────────────────

def test_montecarlo_returns_200(db):
    c = _make_client(db)
    r = c.post("/v1/backtest/montecarlo", json={})
    assert r.status_code == 200
    d = r.json()["data"]
    for key in ("n", "p5", "p50", "p95", "profitable_pct", "histogram"):
        assert key in d
    assert isinstance(d["histogram"], list)


def test_walkforward_returns_200(db):
    c = _make_client(db)
    r = c.post("/v1/backtest/walkforward", json={})
    assert r.status_code == 200
    d = r.json()["data"]
    assert "valid" in d
    assert "windows" in d
    assert isinstance(d["folds"], list)


# ── _build_histogram helper ──────────────────────────────────────────────────

def test_build_histogram_empty_values():
    from src.api.routes.backtest import _build_histogram
    counts, edges = _build_histogram([])
    assert counts == []
    assert edges == []


def test_build_histogram_identical_values():
    from src.api.routes.backtest import _build_histogram
    counts, edges = _build_histogram([2.0, 2.0, 2.0], bins=5)
    assert counts[0] == 3
    assert sum(counts) == 3


def test_build_histogram_varied_values():
    from src.api.routes.backtest import _build_histogram
    counts, edges = _build_histogram([-1.0, 0.0, 1.0, 2.0], bins=4)
    assert sum(counts) == 4
    assert len(edges) == 4


# ── _result_to_out equity loop ───────────────────────────────────────────────

def test_result_to_out_builds_equity_curve(db):
    from src.api.routes.backtest import _result_to_out
    from src.backtest.engine import BacktestResult, BacktestTrade

    trade = BacktestTrade(
        candle_index=0,
        action="BUY",
        entry_price=50_000.0,
        exit_price=51_000.0,
        position_size_pct=2.0,
        pnl_usdt=200.0,
        pnl_pct=0.02,
    )
    result = BacktestResult(
        total_trades=1,
        win_rate=1.0,
        total_pnl_usdt=200.0,
        total_pnl_pct=0.02,
        max_drawdown_pct=0.0,
        sharpe_ratio=1.0,
        profit_factor=None,
        avg_win_pct=2.0,
        avg_loss_pct=0.0,
        trades=[trade],
    )
    out = _result_to_out(result, 10_000.0)
    assert len(out.equity) == 1
    assert out.equity[0].equity == pytest.approx(10_200.0)
    assert out.total_trades == 1


# ── _run_job error path ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_job_marks_error_on_exchange_failure(db):
    from src.api.routes.backtest import _insert_running, _run_job

    class _FailingExchange:
        async def fetch_ohlcv(self, *a, **kw):
            raise RuntimeError("exchange timeout")

    job_id = "job_async_fail"
    _insert_running(job_id, BacktestConfigIn())
    await _run_job(job_id, BacktestConfigIn(), _FailingExchange(), 10_000.0)

    with connection() as conn:
        row = conn.execute("SELECT * FROM backtest_jobs WHERE id=?", (job_id,)).fetchone()
    assert row["status"] == "error"
    assert "exchange timeout" in row["error"]
