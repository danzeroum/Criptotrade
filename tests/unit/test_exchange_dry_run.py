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


# --------------------------------------------------------- per-symbol pricing
def test_dry_run_price_differs_per_symbol(dry_run_env, monkeypatch):
    # The whole point: paper analysis must not show every coin at one price.
    monkeypatch.setattr("time.time", lambda: 1_700_000_000.0)
    client = ExchangeClient()
    btc = asyncio.run(client.fetch_ticker("BTC/USDT"))["last"]
    eth = asyncio.run(client.fetch_ticker("ETH/USDT"))["last"]
    sol = asyncio.run(client.fetch_ticker("SOL/USDT"))["last"]
    assert btc != eth != sol and btc != sol  # three distinct price levels
    # Built-in anchors: BTC ~50k, ETH ~3k, SOL ~150 (± oscillation).
    assert eth < btc and sol < eth


def test_dry_run_ohlcv_differs_per_symbol(dry_run_env, monkeypatch):
    monkeypatch.setattr("time.time", lambda: 1_700_000_000.0)
    client = ExchangeClient()
    btc_close = asyncio.run(client.fetch_ohlcv("BTC/USDT", "1h", limit=5))[-1][4]
    eth_close = asyncio.run(client.fetch_ohlcv("ETH/USDT", "1h", limit=5))[-1][4]
    assert btc_close != eth_close


def test_dry_run_per_symbol_is_deterministic(dry_run_env, monkeypatch):
    monkeypatch.setattr("time.time", lambda: 1_700_000_000.0)
    client = ExchangeClient()
    prices = {asyncio.run(client.fetch_ticker("SOL/USDT"))["last"] for _ in range(100)}
    assert len(prices) == 1  # one symbol, one timestamp -> one price, 100x


def test_dry_run_base_prices_env_override(monkeypatch):
    monkeypatch.setenv("EXCHANGE_DRY_RUN", "true")
    monkeypatch.setenv("DRY_RUN_BASE_PRICES", "ETH/USDT=4242,XRP/USDT=0.5")
    monkeypatch.setattr("time.time", lambda: 0.0)  # sin(0)=0 -> last == base
    client = ExchangeClient()
    assert asyncio.run(client.fetch_ticker("ETH/USDT"))["last"] == 4242.0


def test_dry_run_unmapped_symbol_is_stable_and_distinct(dry_run_env, monkeypatch):
    monkeypatch.setattr("time.time", lambda: 0.0)
    client = ExchangeClient()
    ada = asyncio.run(client.fetch_ticker("ADA/USDT"))["last"]
    doge = asyncio.run(client.fetch_ticker("DOGE/USDT"))["last"]
    assert ada > 0 and doge > 0
    assert ada != doge  # unmapped pairs do not collapse onto one value
    assert ada != 50000.0  # and not the BTC default
    # Stable across processes (hashlib, not salted hash()).
    assert ada == asyncio.run(client.fetch_ticker("ADA/USDT"))["last"]


def test_base_price_for_precedence():
    # overrides > built-in defaults > BTC legacy knob > hash fallback
    assert synth.base_price_for("ETH/USDT", 50000, {"ETH/USDT": 1.0}) == 1.0
    assert synth.base_price_for("ETH/USDT", 50000, None) == 3000.0
    assert synth.base_price_for("BTC/USDT", 50000, None) == 50000.0
    assert synth.base_price_for("BTC/USDT", 61000, None) == 61000.0  # legacy knob
    fallback = synth.base_price_for("ADA/USDT", 50000, None)
    assert fallback > 0 and fallback != 50000.0
    assert fallback == synth.base_price_for("ada/usdt", 50000, None)  # case-insensitive


def test_paper_balance_mirrors_initial_capital(dry_run_env, monkeypatch):
    # Paper balance must track the configured capital, not a hardcoded 10000.
    monkeypatch.setenv("INITIAL_CAPITAL", "25000")
    client = ExchangeClient()
    balance = asyncio.run(client.fetch_balance())
    assert balance["USDT"]["total"] == 25000.0
    assert balance["USDT"]["free"] == 25000.0


def test_paper_balance_defaults_to_10k(dry_run_env, monkeypatch):
    monkeypatch.delenv("INITIAL_CAPITAL", raising=False)
    client = ExchangeClient()
    balance = asyncio.run(client.fetch_balance())
    assert balance["USDT"]["total"] == 10000.0
