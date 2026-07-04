"""Exchange client for crypto trading operations."""
from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import logging

import ccxt

from src.core import synthetic_market as synth

logger = logging.getLogger(__name__)


class ExchangeClient:
    """Client for interacting with cryptocurrency exchanges via CCXT.

    Mode is governed by the **mandatory** ``EXCHANGE_DRY_RUN`` env var (no default,
    on purpose — an ambiguous mode in a financial system is unacceptable):

    * ``EXCHANGE_DRY_RUN=true``  → fully offline: deterministic synthetic market
      data, **zero network, no ccxt client instantiated**.
    * ``EXCHANGE_DRY_RUN=false`` → real ccxt client (production only).
    * unset → ``RuntimeError`` at construction (fail loud, never guess).
    """

    def __init__(
        self,
        exchange_id: str = "binance",
        testnet: bool = True,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ) -> None:
        """Initialise the exchange client."""
        self.exchange_id = exchange_id
        self.testnet = testnet

        dry_run_raw = os.environ.get("EXCHANGE_DRY_RUN")
        if dry_run_raw is None:
            raise RuntimeError(
                "EXCHANGE_DRY_RUN não configurado. "
                "Defina EXCHANGE_DRY_RUN=true (dados sintéticos, sem rede) ou "
                "EXCHANGE_DRY_RUN=false (exchange real — apenas produção). "
                "Nunca deixe ambíguo."
            )
        self.dry_run = dry_run_raw.lower() == "true"
        self.base_price = float(os.getenv("DRY_RUN_BASE_PRICE", "50000"))
        # Optional per-symbol overrides (``BTC/USDT=50000,ETH/USDT=3000``). Lets
        # paper analysis differ per coin instead of every pair sharing one price.
        self.base_prices = synth.parse_base_prices(os.getenv("DRY_RUN_BASE_PRICES", ""))

        # Order routing is INDEPENDENT of the market-data source (``dry_run``):
        #   * ORDER_ROUTING=paper (default) → simulated fills (paper trading)
        #   * ORDER_ROUTING=live            → real orders on the exchange
        # This makes the "real price + paper execution" mode explicit:
        # ``EXCHANGE_DRY_RUN=false`` (real market data) + ``ORDER_ROUTING=paper``.
        # Live routing needs a real exchange client, so it is incompatible with
        # dry-run — fail loud rather than silently dropping real orders.
        routing = (os.getenv("ORDER_ROUTING", "paper") or "paper").strip().lower()
        if routing not in {"paper", "live"}:
            raise RuntimeError(f"ORDER_ROUTING inválido: {routing!r}. Use 'paper' ou 'live'.")
        if routing == "live" and self.dry_run:
            raise RuntimeError(
                "ORDER_ROUTING=live exige EXCHANGE_DRY_RUN=false "
                "(ordens reais precisam de dados reais da exchange)."
            )
        self.paper_trading = routing != "live"
        self.simulated_orders: Dict[str, Dict[str, Any]] = {}

        if self.dry_run:
            # Offline: do NOT instantiate ccxt at all — zero network dependency.
            self.exchange = None
            logger.info(
                "ExchangeClient in DRY_RUN (synthetic data, no network)",
                extra={"exchange": exchange_id, "base_price": self.base_price},
            )
            return

        exchange_class = getattr(ccxt, exchange_id)
        config: Dict[str, Any] = {
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        }

        if api_key and api_secret:
            config["apiKey"] = api_key
            config["secret"] = api_secret

        self.exchange = exchange_class(config)

        if testnet and hasattr(self.exchange, "set_sandbox_mode"):
            try:
                self.exchange.set_sandbox_mode(True)
                logger.info("Sandbox mode enabled for %s", exchange_id)
            except Exception as exc:
                logger.warning("Unable to enable sandbox mode", exc_info=exc)

        logger.info(
            "ExchangeClient initialised",
            extra={
                "exchange": exchange_id,
                "testnet": testnet,
                "paper_trading": self.paper_trading,
                "dry_run": self.dry_run,
            },
        )

    @staticmethod
    def _now_ts() -> int:
        """Mockable timestamp source (tests patch ``time.time``)."""
        return int(time.time())

    def _base_for(self, symbol: str) -> float:
        """Resolve the synthetic base price for ``symbol`` (per-symbol in dry-run)."""
        return synth.base_price_for(symbol, self.base_price, self.base_prices)

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch current ticker data for a symbol."""
        if self.dry_run:
            return synth.synthetic_ticker(symbol, self._base_for(symbol), self._now_ts())
        try:
            ticker = await asyncio.to_thread(self.exchange.fetch_ticker, symbol)
            logger.debug("Fetched ticker for %s: %s", symbol, ticker.get("last"))
            return ticker
        except Exception as exc:  # pragma: no cover - network guard
            logger.error("Error fetching ticker for %s", symbol, exc_info=exc)
            raise

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ) -> List[List[float]]:
        """Fetch OHLCV (candlestick) data."""
        if self.dry_run:
            return synth.synthetic_ohlcv(
                self._base_for(symbol), self._now_ts(), timeframe, limit
            )
        try:
            ohlcv = await asyncio.to_thread(
                self.exchange.fetch_ohlcv, symbol, timeframe, None, limit
            )
            logger.debug("Fetched %s candles for %s (%s)", len(ohlcv), symbol, timeframe)
            return ohlcv
        except Exception as exc:  # pragma: no cover - network guard
            logger.error("Error fetching OHLCV for %s", symbol, exc_info=exc)
            raise

    async def fetch_order_book(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """Fetch order book (bids and asks)."""
        if self.dry_run:
            return synth.synthetic_order_book(
                symbol, self._base_for(symbol), self._now_ts(), limit
            )
        try:
            order_book = await asyncio.to_thread(
                self.exchange.fetch_order_book, symbol, limit
            )
            logger.debug("Fetched order book for %s", symbol)
            return order_book
        except Exception as exc:  # pragma: no cover - network guard
            logger.error("Error fetching order book for %s", symbol, exc_info=exc)
            raise

    async def fetch_balance(self) -> Dict[str, Any]:
        """Fetch account balance."""
        if self.paper_trading:
            # Paper balance mirrors the configured capital so what the API and
            # dashboards show stays coherent with position sizing.
            try:
                capital = float(os.getenv("INITIAL_CAPITAL", "10000"))
            except ValueError:
                capital = 10000.0
            return {
                "USDT": {"free": capital, "used": 0.0, "total": capital},
                "BTC": {"free": 0.0, "used": 0.0, "total": 0.0},
            }

        try:
            balance = await asyncio.to_thread(self.exchange.fetch_balance)
            logger.debug("Fetched account balance")
            return balance
        except Exception as exc:  # pragma: no cover - network guard
            logger.error("Error fetching balance", exc_info=exc)
            raise

    async def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a trading order."""
        if self.paper_trading:
            return await self._create_paper_order(symbol, order_type, side, amount, price, params)

        try:
            order = await asyncio.to_thread(
                self.exchange.create_order,
                symbol,
                order_type,
                side,
                amount,
                price,
                params or {},
            )
            logger.info(
                "Created %s %s order for %s %s at %s",
                order_type,
                side,
                amount,
                symbol,
                price or "market",
            )
            return order
        except Exception as exc:  # pragma: no cover - network guard
            logger.error("Error creating order", exc_info=exc)
            raise

    async def _create_paper_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create simulated order for paper trading."""
        import uuid

        order_id = f"PAPER_{uuid.uuid4().hex[:8]}"
        ticker = await self.fetch_ticker(symbol)
        market_price = ticker.get("last", 0.0) or ticker.get("close", 0.0)

        if order_type == "limit" and price:
            execution_price = price
            status = "open"
        else:
            execution_price = market_price
            status = "filled"

        slippage = 0.002
        if side.lower() == "buy":
            execution_price *= 1 + slippage
        else:
            execution_price *= 1 - slippage

        fee_rate = 0.001
        fee_amount = amount * execution_price * fee_rate

        order = {
            "id": order_id,
            "symbol": symbol,
            "type": order_type,
            "side": side,
            "amount": amount,
            "price": execution_price,
            "average": execution_price,
            "filled": amount if status == "filled" else 0.0,
            "remaining": 0.0 if status == "filled" else amount,
            "status": status,
            "fee": {"cost": fee_amount, "currency": "USDT"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "datetime": datetime.now(timezone.utc).isoformat(),
            "info": {"paper_trading": True},
        }

        self.simulated_orders[order_id] = order
        logger.info(
            "[PAPER] Created %s %s order: %s %s @ %.2f (ID: %s)",
            order_type,
            side,
            amount,
            symbol,
            execution_price,
            order_id,
        )
        return order

    async def fetch_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Fetch order status."""
        if self.paper_trading and order_id in self.simulated_orders:
            return self.simulated_orders[order_id]

        try:
            order = await asyncio.to_thread(self.exchange.fetch_order, order_id, symbol)
            logger.debug("Fetched order %s status: %s", order_id, order.get("status"))
            return order
        except Exception as exc:  # pragma: no cover - network guard
            logger.error("Error fetching order %s", order_id, exc_info=exc)
            raise

    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Cancel an open order."""
        if self.paper_trading and order_id in self.simulated_orders:
            order = self.simulated_orders[order_id]
            if order.get("status") == "open":
                order["status"] = "canceled"
                logger.info("[PAPER] Canceled order %s", order_id)
            return order

        try:
            result = await asyncio.to_thread(self.exchange.cancel_order, order_id, symbol)
            logger.info("Canceled order %s", order_id)
            return result
        except Exception as exc:  # pragma: no cover - network guard
            logger.error("Error canceling order %s", order_id, exc_info=exc)
            raise

    async def get_markets(self) -> Dict[str, Any]:
        """Get available trading markets/symbols."""
        try:
            markets = await asyncio.to_thread(self.exchange.load_markets)
            logger.debug("Loaded %s markets", len(markets))
            return markets
        except Exception as exc:  # pragma: no cover - network guard
            logger.error("Error loading markets", exc_info=exc)
            raise

    async def is_symbol_valid(self, symbol: str) -> bool:
        """Check if a symbol is valid and tradeable."""
        try:
            markets = await self.get_markets()
            market = markets.get(symbol)
            return bool(market and market.get("active", False))
        except Exception:
            return False
