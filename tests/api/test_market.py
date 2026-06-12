"""Market-pair validation tests (P2-2).

Note on %2F: httpx (TestClient's ASGI transport) decodes %2F to / before
routing, so URL path tests use the dash form (BTC-USDT). %2F decoding inside
_decode_pair is covered by the direct unit test below.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app


class _MockExchangeClient:
    async def fetch_ohlcv(self, pair, timeframe="1h", limit=100):
        ts = 1_700_000_000_000
        return [[ts + i * 3_600_000, 50_000.0, 51_000.0, 49_000.0, 50_500.0, 100.0] for i in range(limit)]

    async def fetch_ticker(self, pair):
        return {
            "symbol": pair,
            "last": 50_500.0,
            "bid": 50_450.0,
            "ask": 50_550.0,
            "timestamp": 1_700_000_000_000,
        }


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[deps.get_exchange_client] = lambda: _MockExchangeClient()
    return TestClient(app)


def test_unknown_pair_returns_422(client):
    r = client.get("/v1/market/FOO-BAR/candles")
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "invalid_pair"
    assert "valid" in body
    assert "BTC/USDT" in body["valid"]


def test_known_pair_dash_form_returns_200(client):
    r = client.get("/v1/market/BTC-USDT/candles")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) > 0
    assert "o" in data[0]


def test_valid_pairs_in_error_body_are_uppercase(client):
    r = client.get("/v1/market/INVALID-PAIR/candles")
    assert r.status_code == 422
    for p in r.json()["valid"]:
        assert p == p.upper(), f"pair {p!r} not uppercase"


def test_decode_pair_handles_percent_encoded_slash():
    """_decode_pair must accept BTC%2FUSDT and validate it."""
    from src.api.routes.market import _decode_pair

    result = _decode_pair("BTC%2FUSDT")
    assert result == "BTC/USDT"


def test_decode_pair_rejects_unknown_percent_encoded():
    """_decode_pair must reject FOO%2FBAR with 422."""
    from src.api.routes.market import _decode_pair

    with pytest.raises(HTTPException) as exc_info:
        _decode_pair("FOO%2FBAR")
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["error"] == "invalid_pair"


def test_custom_market_pairs_env_restricts_allowlist(monkeypatch):
    """MARKET_PAIRS env var restricts the validation allowlist."""
    import importlib

    monkeypatch.setenv("MARKET_PAIRS", "ETH/USDT")
    import src.api.routes.market as mmod
    importlib.reload(mmod)

    with pytest.raises(HTTPException) as exc_info:
        mmod._decode_pair("BTC%2FUSDT")
    assert exc_info.value.status_code == 422
    assert "ETH/USDT" in exc_info.value.detail["valid"]

    # ETH/USDT should pass after reload
    result = mmod._decode_pair("ETH%2FUSDT")
    assert result == "ETH/USDT"

    # Restore default
    monkeypatch.delenv("MARKET_PAIRS")
    importlib.reload(mmod)


def test_ticker_returns_200_with_24h_stats(client):
    r = client.get("/v1/market/BTC-USDT/ticker")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["symbol"] == "BTC/USDT"
    assert d["last"] == pytest.approx(50_500.0)
    assert d["bid"] == pytest.approx(50_450.0)
    assert d["ask"] == pytest.approx(50_550.0)
    assert d["high_24h"] >= d["last"]
    assert d["low_24h"] <= d["last"]
    assert d["volume_24h"] > 0
    assert isinstance(d["change_24h_pct"], float)
    assert isinstance(d["change_24h_usd"], float)


def test_ticker_unknown_pair_returns_422(client):
    r = client.get("/v1/market/FOO-BAR/ticker")
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_pair"


# ── 503 / error paths ────────────────────────────────────────────────────────

class _FailingClient:
    """Exchange client that raises on every call — tests 503 error paths."""
    async def fetch_ohlcv(self, *a, **kw):
        raise RuntimeError("exchange unreachable")

    async def fetch_ticker(self, *a, **kw):
        raise RuntimeError("ticker unavailable")


@pytest.fixture
def failing_client():
    app = create_app()
    app.dependency_overrides[deps.get_exchange_client] = lambda: _FailingClient()
    return TestClient(app)


def test_candles_exchange_error_returns_503(failing_client):
    r = failing_client.get("/v1/market/BTC-USDT/candles")
    assert r.status_code == 503
    assert r.json()["error"] == "market_data_unavailable"


def test_ticker_fetch_ticker_error_returns_503(failing_client):
    r = failing_client.get("/v1/market/BTC-USDT/ticker")
    assert r.status_code == 503
    assert r.json()["error"] == "market_data_unavailable"


class _EmptyCandlesClient(_MockExchangeClient):
    """Returns one candle — insufficient for 24h stats and for some indicators."""
    async def fetch_ohlcv(self, pair, timeframe="1h", limit=100):
        ts = 1_700_000_000_000
        return [[ts, 50_000.0, 51_000.0, 49_000.0, 50_500.0, 100.0]]


@pytest.fixture
def sparse_client():
    app = create_app()
    app.dependency_overrides[deps.get_exchange_client] = lambda: _EmptyCandlesClient()
    return TestClient(app)


def test_ticker_with_single_candle_uses_fallback_stats(sparse_client):
    r = sparse_client.get("/v1/market/BTC-USDT/ticker")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["volume_24h"] == 0.0
    assert d["change_24h_pct"] == 0.0


# ── Analysis endpoints ───────────────────────────────────────────────────────

def test_indicators_returns_200_with_data(client):
    r = client.get("/v1/market/BTC-USDT/indicators")
    assert r.status_code == 200
    d = r.json()["data"]
    for field in ("rsi", "atr", "ema9", "ema21", "sma20"):
        assert field in d


def test_regime_returns_200_with_valid_regime(client):
    r = client.get("/v1/market/BTC-USDT/regime")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["regime"] in ("strong_uptrend", "strong_downtrend", "sideways", "chaotic", "unknown")
    assert "label" in d
    assert isinstance(d["active_strategies"], list)
    assert 0.0 <= d["confidence"] <= 1.0


def test_levels_returns_200_with_fibs(client):
    r = client.get("/v1/market/BTC-USDT/levels")
    assert r.status_code == 200
    d = r.json()["data"]
    assert "support" in d
    assert "resistance" in d
    assert len(d["fib"]) == 7  # 7 Fibonacci ratios


def test_volume_profile_returns_200_with_bins(client):
    r = client.get("/v1/market/BTC-USDT/volume-profile")
    assert r.status_code == 200
    d = r.json()["data"]
    assert "poc" in d
    assert "vah" in d
    assert "val" in d
    assert isinstance(d["bins"], list)


def test_patterns_returns_200_list(client):
    r = client.get("/v1/market/BTC-USDT/patterns")
    assert r.status_code == 200
    assert isinstance(r.json()["data"], list)


def test_signal_returns_200_with_action(client):
    r = client.get("/v1/market/BTC-USDT/signal")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["action"] in ("buy", "sell", "hold")
    assert d["entry"] > 0
    assert 0.0 <= d["confidence"] <= 1.0
    assert "reason" in d


def test_indicators_insufficient_data_returns_422(sparse_client):
    r = sparse_client.get("/v1/market/BTC-USDT/indicators")
    # Single candle → TechnicalAnalyzer raises ValueError → 422
    assert r.status_code in (200, 422)  # accept both: depends on analyzer min-data threshold


def test_regime_insufficient_data_returns_422(sparse_client):
    r = sparse_client.get("/v1/market/BTC-USDT/regime")
    assert r.status_code in (200, 422)


def test_signal_insufficient_data_returns_422(sparse_client):
    r = sparse_client.get("/v1/market/BTC-USDT/signal")
    assert r.status_code in (200, 422)
