"""Phase 4b-i — EXCHANGE_DRY_RUN: synthetic data, zero network, fail-loud env."""
from __future__ import annotations

import asyncio

import pytest

from src.core import synthetic_market as synth
from src.core.exchange_client import ExchangeClient


@pytest.fixture
def dry_run_env(monkeypatch):
    monkeypatch.setenv("EXCHANGE_DRY_RUN", "true")
    monkeypatch.setenv("DRY_RUN_BASE_PRICE", "50000")


# ----------------------------------------------------------- mandatory env
def test_missing_env_raises_on_init(monkeypatch):
    monkeypatch.delenv("EXCHANGE_DRY_RUN", raising=False)
    with pytest.raises(RuntimeError, match="EXCHANGE_DRY_RUN"):
        ExchangeClient()


def test_dry_run_does_not_instantiate_ccxt(dry_run_env):
    client = ExchangeClient()
    assert client.dry_run is True
    assert client.exchange is None  # zero ccxt client in offline mode


# ----------------------------------------------------------- zero network
def test_dry_run_fetch_ticker_no_network(dry_run_env, monkeypatch):
    import src.core.exchange_client as ec

    # Any access to ccxt would be a bug in dry-run: make it explode if touched.
    class _Boom:
        def __getattr__(self, _name):
            raise AssertionError("ccxt must not be used in DRY_RUN")

    monkeypatch.setattr(ec, "ccxt", _Boom())
    client = ExchangeClient()
    ticker = asyncio.run(client.fetch_ticker("BTC/USDT"))
    assert ticker["info"]["dry_run"] is True
    assert ticker["last"] > 0


# ----------------------------------------------------------- determinism
def test_dry_run_price_is_deterministic(dry_run_env, monkeypatch):
    monkeypatch.setattr("time.time", lambda: 1_700_000_000.0)
    client = ExchangeClient()
    prices = {asyncio.run(client.fetch_ticker("BTC/USDT"))["last"] for _ in range(100)}
    assert len(prices) == 1  # same timestamp -> identical price, 100x


def test_synthetic_price_pure_function():
    # Pure function of (base, ts): no randomness, fully reproducible.
    assert synth.synthetic_price(50000, 1_700_000_000) == synth.synthetic_price(
        50000, 1_700_000_000
    )
    assert synth.synthetic_price(50000, 0) == 50000.0  # sin(0) == 0


def test_dry_run_ohlcv_and_order_book(dry_run_env, monkeypatch):
    monkeypatch.setattr("time.time", lambda: 1_700_000_000.0)
    client = ExchangeClient()
    candles = asyncio.run(client.fetch_ohlcv("BTC/USDT", "1h", limit=10))
    assert len(candles) == 10
    assert all(len(c) == 6 for c in candles)  # [ts, o, h, l, c, v]
    book = asyncio.run(client.fetch_order_book("BTC/USDT", limit=5))
    assert len(book["bids"]) == 5 and len(book["asks"]) == 5
    assert book["bids"][0][0] < book["asks"][0][0]  # bid below ask
