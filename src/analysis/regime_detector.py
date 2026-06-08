"""Market regime detection.

Classifies the current market environment so the correct strategy is applied.
Murphy: "Grid works in consolidation. Trend strategies lose in ranges."

Regimes:
  strong_uptrend   — EMA spread > 2% and bullish
  strong_downtrend — EMA spread > 2% and bearish
  sideways         — EMA spread < 1% and low volatility
  chaotic          — ATR/price > 5% (extreme volatility)
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_REGIME_STRATEGY_MAP = {
    "strong_uptrend": ["dca"],
    "strong_downtrend": [],        # no long strategies in downtrend
    "sideways": ["grid", "dca"],
    "chaotic": [],                 # no trading during extreme volatility
    "unknown": ["dca"],            # default fallback
}


def detect_regime(
    ema_fast: float | None,
    ema_slow: float | None,
    atr: float | None,
    current_price: float | None,
) -> str:
    """Classify market regime from pre-computed indicator values.

    Returns one of: "strong_uptrend", "strong_downtrend", "sideways",
    "chaotic", "unknown".
    """
    if not all([ema_fast, ema_slow, current_price]):
        return "unknown"

    ema_spread = abs(ema_fast - ema_slow) / current_price

    volatility_pct = (atr / current_price) if atr and current_price else 0.0

    if volatility_pct > 0.05:
        return "chaotic"

    if ema_spread > 0.02:
        return "strong_uptrend" if ema_fast > ema_slow else "strong_downtrend"

    if ema_spread < 0.01 and volatility_pct < 0.02:
        return "sideways"

    # Transitional — mild trend
    return "strong_uptrend" if ema_fast > ema_slow else "strong_downtrend"


def strategies_for_regime(regime: str) -> list[str]:
    """Return the list of strategy keys appropriate for a given regime."""
    return list(_REGIME_STRATEGY_MAP.get(regime, ["dca"]))


def detect_market_extreme(
    rsi: float | None,
    volume_ratio: float | None,
) -> str | None:
    """Detect euphoria or panic based on RSI and volume.

    Murphy: "Euphoria and panic create the most predictable opportunities."

    Returns:
        "EUFORIA — possível topo" | "PÂNICO — possível fundo" | None
    """
    if rsi is None or volume_ratio is None:
        return None
    if rsi > 75 and volume_ratio > 2.0:
        return "EUFORIA — possível topo"
    if rsi < 25 and volume_ratio > 2.0:
        return "PÂNICO — possível fundo"
    return None
