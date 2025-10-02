"""Exchange client for crypto trading operations."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import logging

import ccxt

logger = logging.getLogger(__name__)


class ExchangeClient:
    """Client for interacting with cryptocurrency exchanges via CCXT."""

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

        self.paper_trading = True
        self.simulated_orders: Dict[str, Dict[str, Any]] = {}

        logger.info(
            "ExchangeClient initialised",
            extra={
                "exchange": exchange_id,
                "testnet": testnet,
                "paper_trading": self.paper_trading,
            },
        )

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch current ticker data for a symbol."""
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
            return {
                "USDT": {"free": 10000.0, "used": 0.0, "total": 10000.0},
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
