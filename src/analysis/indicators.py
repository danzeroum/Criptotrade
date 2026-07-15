"""Technical indicators computed from OHLCV data.

OHLCV format (CCXT standard): List[List[float]]
Each row: [timestamp_ms, open, high, low, close, volume]
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TechnicalIndicators:
    """Snapshot of all computed technical indicators for the latest candle."""

    # Trend — Murphy: SMAs/EMAs for regime classification
    sma_20: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    ema_fast: float | None = None   # EMA(9)
    ema_slow: float | None = None   # EMA(21)

    # Momentum
    rsi: float | None = None               # RSI(14)
    stochastic_k: float | None = None      # Stochastic %K (14,3,3)
    stochastic_d: float | None = None      # Stochastic %D

    # Trend + Momentum
    macd_line: float | None = None         # MACD(12,26,9)
    macd_signal: float | None = None
    macd_hist: float | None = None

    # Volatility
    bb_upper: float | None = None          # Bollinger Bands (20, 2σ)
    bb_middle: float | None = None
    bb_lower: float | None = None
    bb_percent: float | None = None        # %B oscillator

    atr: float | None = None               # ATR(14)

    # Volume
    volume_ratio: float | None = None      # current / ma_volume_20
    obv: float | None = None               # On-Balance Volume

    # Raw price (convenience)
    current_price: float | None = None


def _safe_float(series: pd.Series, idx: int = -1) -> float | None:
    """Return the float at index or None if NaN/out-of-bounds."""
    try:
        val = float(series.iloc[idx])
        return None if np.isnan(val) else val
    except (IndexError, TypeError, ValueError):
        return None


class TechnicalAnalyzer:
    """Compute indicators from raw OHLCV data.

    Requires at least 50 candles for meaningful indicator values.
    Indicators are computed directly with numpy/pandas (no third-party `ta`).
    """

    MIN_CANDLES = 50

    def __init__(self, ohlcv: list[list[float]]) -> None:
        if len(ohlcv) < self.MIN_CANDLES:
            raise ValueError(
                f"Need at least {self.MIN_CANDLES} candles, got {len(ohlcv)}"
            )
        self._df = self._build_df(ohlcv)
        self._compute()

    @staticmethod
    def _build_df(ohlcv: list[list[float]]) -> pd.DataFrame:
        df = pd.DataFrame(
            ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.set_index("timestamp").sort_index()
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def _compute(self) -> None:
        """Calculate all indicators and attach to the dataframe."""
        df = self._df
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # --- Trend: SMA / EMA ---
        df["sma_20"] = close.rolling(20).mean()
        df["sma_50"] = close.rolling(50).mean()
        df["sma_200"] = close.rolling(200).mean() if len(df) >= 200 else pd.Series(dtype=float)
        df["ema_fast"] = close.ewm(span=9, adjust=False).mean()
        df["ema_slow"] = close.ewm(span=21, adjust=False).mean()

        # --- Momentum: RSI ---
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["rsi"] = 100 - (100 / (1 + rs))

        # --- Momentum: Stochastic (14,3,3) ---
        low_14 = low.rolling(14).min()
        high_14 = high.rolling(14).max()
        denom = (high_14 - low_14).replace(0, np.nan)
        df["stoch_k_raw"] = 100 * (close - low_14) / denom
        df["stochastic_k"] = df["stoch_k_raw"].rolling(3).mean()
        df["stochastic_d"] = df["stochastic_k"].rolling(3).mean()

        # --- Trend+Momentum: MACD (12,26,9) ---
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        df["macd_line"] = ema12 - ema26
        df["macd_signal"] = df["macd_line"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd_line"] - df["macd_signal"]

        # --- Volatility: Bollinger Bands (20, 2σ) ---
        df["bb_middle"] = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        df["bb_upper"] = df["bb_middle"] + 2 * bb_std
        df["bb_lower"] = df["bb_middle"] - 2 * bb_std
        bb_range = (df["bb_upper"] - df["bb_lower"]).replace(0, np.nan)
        df["bb_percent"] = (close - df["bb_lower"]) / bb_range

        # --- Volatility: ATR (14) ---
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = tr.ewm(com=13, adjust=False).mean()

        # --- Volume: ratio and OBV ---
        df["vol_ma_20"] = volume.rolling(20).mean()
        df["volume_ratio"] = volume / df["vol_ma_20"].replace(0, np.nan)
        obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
        df["obv"] = obv

    def get_latest(self) -> TechnicalIndicators:
        """Return indicators for the most recent candle."""
        df = self._df
        return TechnicalIndicators(
            current_price=_safe_float(df["close"]),
            sma_20=_safe_float(df["sma_20"]),
            sma_50=_safe_float(df["sma_50"]),
            sma_200=_safe_float(df.get("sma_200", pd.Series(dtype=float))),
            ema_fast=_safe_float(df["ema_fast"]),
            ema_slow=_safe_float(df["ema_slow"]),
            rsi=_safe_float(df["rsi"]),
            stochastic_k=_safe_float(df["stochastic_k"]),
            stochastic_d=_safe_float(df["stochastic_d"]),
            macd_line=_safe_float(df["macd_line"]),
            macd_signal=_safe_float(df["macd_signal"]),
            macd_hist=_safe_float(df["macd_hist"]),
            bb_upper=_safe_float(df["bb_upper"]),
            bb_middle=_safe_float(df["bb_middle"]),
            bb_lower=_safe_float(df["bb_lower"]),
            bb_percent=_safe_float(df["bb_percent"]),
            atr=_safe_float(df["atr"]),
            volume_ratio=_safe_float(df["volume_ratio"]),
            obv=_safe_float(df["obv"]),
        )

    def get_series(self, column: str) -> pd.Series:
        """Return the full series for a computed column (e.g. 'rsi', 'macd_hist')."""
        return self._df.get(column, pd.Series(dtype=float))


@dataclass
class DivergenceResult:
    """Result of a divergence check."""
    detected: bool
    kind: str | None   # "bullish_divergence" | "bearish_divergence"
    description: str


class DivergenceDetector:
    """Detect price/indicator divergences — a leading signal of trend exhaustion.

    Bullish divergence: price makes lower low, indicator makes higher low.
    Bearish divergence: price makes higher high, indicator makes lower high.
    """

    def __init__(self, lookback: int = 20) -> None:
        self.lookback = lookback

    def check_rsi_price(
        self, ohlcv: list[list[float]], rsi_series: pd.Series
    ) -> DivergenceResult:
        """Check for RSI / price divergence over the last ``lookback`` candles."""
        closes = [c[4] for c in ohlcv[-self.lookback:]]
        rsi_vals = rsi_series.dropna().values[-self.lookback:]

        if len(closes) < 4 or len(rsi_vals) < 4:
            return DivergenceResult(False, None, "insufficient data")

        price_low_1 = min(closes[: len(closes) // 2])
        price_low_2 = min(closes[len(closes) // 2 :])
        rsi_low_1 = min(rsi_vals[: len(rsi_vals) // 2])
        rsi_low_2 = min(rsi_vals[len(rsi_vals) // 2 :])

        price_high_1 = max(closes[: len(closes) // 2])
        price_high_2 = max(closes[len(closes) // 2 :])
        rsi_high_1 = max(rsi_vals[: len(rsi_vals) // 2])
        rsi_high_2 = max(rsi_vals[len(rsi_vals) // 2 :])

        if price_low_2 < price_low_1 and rsi_low_2 > rsi_low_1:
            return DivergenceResult(
                True, "bullish_divergence",
                f"Price lower low ({price_low_2:.2f} < {price_low_1:.2f}) but RSI higher low"
            )

        if price_high_2 > price_high_1 and rsi_high_2 < rsi_high_1:
            return DivergenceResult(
                True, "bearish_divergence",
                f"Price higher high ({price_high_2:.2f} > {price_high_1:.2f}) but RSI lower high"
            )

        return DivergenceResult(False, None, "no divergence")

    def check_macd_price(
        self, ohlcv: list[list[float]], macd_hist: pd.Series
    ) -> DivergenceResult:
        """Check for MACD histogram / price divergence."""
        closes = [c[4] for c in ohlcv[-self.lookback:]]
        hist_vals = macd_hist.dropna().values[-self.lookback:]

        if len(closes) < 4 or len(hist_vals) < 4:
            return DivergenceResult(False, None, "insufficient data")

        half = len(closes) // 2
        price_low_1 = min(closes[:half])
        price_low_2 = min(closes[half:])
        hist_low_1 = min(hist_vals[: len(hist_vals) // 2])
        hist_low_2 = min(hist_vals[len(hist_vals) // 2 :])

        if price_low_2 < price_low_1 and hist_low_2 > hist_low_1:
            return DivergenceResult(
                True, "bullish_divergence",
                "Price lower low but MACD histogram higher low"
            )

        price_high_1 = max(closes[:half])
        price_high_2 = max(closes[half:])
        hist_high_1 = max(hist_vals[: len(hist_vals) // 2])
        hist_high_2 = max(hist_vals[len(hist_vals) // 2 :])

        if price_high_2 > price_high_1 and hist_high_2 < hist_high_1:
            return DivergenceResult(
                True, "bearish_divergence",
                "Price higher high but MACD histogram lower high"
            )

        return DivergenceResult(False, None, "no divergence")


@dataclass
class TrendAlignment:
    """Multi-timeframe trend alignment (Dow Theory)."""
    primary: str       # weekly
    secondary: str     # daily
    minor: str         # hourly
    aligned: bool      # True if all three agree
    direction: str | None  # "bullish" | "bearish" | None (mixed)


class MultiTimeframeTrend:
    """Classify trend across three timeframes using EMA(9) vs EMA(21).

    Murphy: "Never trade against the primary trend. Secondary and minor trends
    must align with the primary before entering a position."
    """

    TIMEFRAMES = {
        "primary": "1w",
        "secondary": "1d",
        "minor": "1h",
    }

    async def classify(self, symbol: str, exchange_client: Any) -> TrendAlignment:
        """Fetch OHLCV for each timeframe and classify the trend."""
        results: dict[str, str] = {}
        for label, tf in self.TIMEFRAMES.items():
            try:
                ohlcv = await exchange_client.fetch_ohlcv(symbol, tf, limit=50)
                if len(ohlcv) < TechnicalAnalyzer.MIN_CANDLES:
                    results[label] = "unknown"
                    continue
                analyzer = TechnicalAnalyzer(ohlcv)
                ind = analyzer.get_latest()
                if ind.ema_fast is None or ind.ema_slow is None:
                    results[label] = "unknown"
                else:
                    results[label] = "bullish" if ind.ema_fast > ind.ema_slow else "bearish"
            except Exception as exc:
                logger.warning("MTF trend fetch failed for %s %s: %s", symbol, tf, exc)
                results[label] = "unknown"

        primary = results.get("primary", "unknown")
        secondary = results.get("secondary", "unknown")
        minor = results.get("minor", "unknown")

        known = [t for t in (primary, secondary, minor) if t != "unknown"]
        aligned = len(set(known)) == 1 and len(known) == 3
        direction = known[0] if aligned else None

        return TrendAlignment(
            primary=primary,
            secondary=secondary,
            minor=minor,
            aligned=aligned,
            direction=direction,
        )
