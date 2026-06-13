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


# ----------------------------------------------------- pairs + ticker endpoints
def test_pairs_returns_sorted_allowlist(client):
    r = client.get("/v1/market/pairs")
    assert r.status_code == 200
    pairs = r.json()["data"]
    assert "BTC/USDT" in pairs
    assert pairs == sorted(pairs)  # stable order for the dropdown


def test_ticker_returns_price_and_24h(client):
    r = client.get("/v1/market/BTC-USDT/ticker")
    assert r.status_code == 200
    t = r.json()["data"]
    # Mock candles are constant: last close 50500, high 51000, low 49000.
    assert t["last"] == 50_500.0
    assert t["high_24h"] == 51_000.0
    assert t["low_24h"] == 49_000.0
    assert t["change_24h_pct"] == 0.0  # constant closes -> flat


def test_ticker_unknown_pair_returns_422(client):
    r = client.get("/v1/market/FOO-BAR/ticker")
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_pair"


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
