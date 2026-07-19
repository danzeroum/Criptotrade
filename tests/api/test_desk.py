"""N2 — GET /v1/desk/summary: the Mesa Multi-Ativo batch snapshot.

One request covers every operated pair with price, signal (action+confidence),
open position (side + unrealized P&L) and the header aggregates (slots, capital,
active signals). Dry-run => synthetic OHLCV, so no network. Also covers the
confidence propagation into signal_generated and demo read access.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.api.routes import desk
from src.core.db import init_db
from src.orchestration.position_store import PositionStore

_POS = {
    "stop_loss": None, "take_profit": None,
    "opened_at": "2026-01-01T00:00:00+00:00",
}


@pytest.fixture
def desk_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.delenv("AUTH_MODE", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.setenv("EXCHANGE_DRY_RUN", "true")  # synthetic OHLCV, no network
    monkeypatch.setenv("MARKET_PAIRS", "BTC/USDT,ETH/USDT,SOL/USDT")
    monkeypatch.setenv("SYMBOLS", "BTC/USDT,ETH/USDT,SOL/USDT")
    monkeypatch.setenv("INITIAL_CAPITAL", "10000")
    monkeypatch.setenv("MAX_CONCURRENT_POSITIONS", "3")
    init_db()
    deps.reset_singletons()  # fresh ledger/exchange singletons on this tmp db
    desk._OHLCV_CACHE.clear()  # module-level TTL cache must not leak across tests
    yield deps.get_ledger()
    deps.reset_singletons()
    desk._OHLCV_CACHE.clear()


def _summary(client: TestClient) -> dict:
    r = client.get("/v1/desk/summary")
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_batch_returns_every_operated_pair(desk_env):
    data = _summary(TestClient(create_app()))
    syms = {row["symbol"] for row in data["rows"]}
    assert syms == {"BTC/USDT", "ETH/USDT", "SOL/USDT"}
    # Price + freshness derived from (synthetic) OHLCV.
    for row in data["rows"]:
        assert row["last"] is not None
        assert row["as_of"] is not None


def test_signal_action_and_confidence_surface(desk_env):
    ledger = desk_env
    ledger.log_signal(agent="strategy",
                      signal={"symbol": "BTC/USDT", "action": "buy"}, confidence=0.82)
    data = _summary(TestClient(create_app()))
    btc = next(r for r in data["rows"] if r["symbol"] == "BTC/USDT")
    assert btc["signal_action"] == "buy"
    assert btc["signal_confidence"] == 0.82
    assert btc["last_cycle_at"] is not None
    assert data["signals_active"] == 1  # confidence >= 0.6


def test_open_position_and_unrealized_pnl(desk_env):
    ledger = desk_env
    # A BTC buy lot far below any synthetic price → unrealized P&L is computable.
    PositionStore(lambda: ledger.db_path).upsert(
        "o1", {"symbol": "BTC/USDT", "side": "buy", "entry_price": 1.0, "quantity": 2.0, **_POS})
    data = _summary(TestClient(create_app()))
    btc = next(r for r in data["rows"] if r["symbol"] == "BTC/USDT")
    assert btc["position_side"] == "buy"
    assert btc["position_qty"] == 2.0
    assert btc["unrealized_pnl"] is not None
    assert data["slots_used"] == 1
    assert data["slots_max"] == 3
    assert data["capital_allocated"] == 2.0  # entry 1.0 * qty 2.0
    assert data["capital_free"] == 9998.0


def test_actionable_rows_sort_first(desk_env):
    ledger = desk_env
    ledger.log_signal(agent="strategy",
                      signal={"symbol": "SOL/USDT", "action": "buy"}, confidence=0.9)
    data = _summary(TestClient(create_app()))
    # SOL has the only strong signal → it must be the first row.
    assert data["rows"][0]["symbol"] == "SOL/USDT"


def test_demo_principal_can_read(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_MODE", "demo")
    monkeypatch.setenv("EXCHANGE_DRY_RUN", "true")
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.setenv("SYMBOLS", "BTC/USDT")
    init_db()
    deps.reset_singletons()
    r = TestClient(create_app()).get("/v1/desk/summary")
    assert r.status_code == 200, r.text
    assert "rows" in r.json()["data"]
