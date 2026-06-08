"""Strategy agent for generating trading signals."""
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from src.agents.base_agent import BaseAgent
from src.analysis.indicators import TechnicalAnalyzer, DivergenceDetector
from src.analysis.support_resistance import SupportResistanceDetector
from src.analysis.volume_profile import VolumeProfile
from src.analysis.regime_detector import detect_regime, strategies_for_regime, detect_market_extreme

logger = logging.getLogger(__name__)


class StrategyAgent(BaseAgent):
    """Generates trading signals using real technical analysis.

    Requires an ExchangeClient (injected) to fetch live / synthetic OHLCV data.
    The active strategy is resolved from the strategy registry based on the
    detected market regime.
    """

    def __init__(self, exchange_client: Any = None) -> None:
        super().__init__("strategy")
        self.tools = ["market_data", "technical_indicators", "pattern_recognition"]
        self.exchange_client = exchange_client
        self._sr_detector = SupportResistanceDetector()
        self._div_detector = DivergenceDetector()
        # Strategy instances loaded lazily to avoid circular imports
        self._strategy_cache: Dict[str, Any] = {}

    # ---------------------------------------------------------------------- public

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze market and generate a trading signal."""
        if not self.validate_input(task):
            raise ValueError("Invalid strategy task")

        symbol = task.get("symbol", "BTC/USDT")
        timeframe = task.get("timeframe", "1h")

        analysis = await self._analyze_market(symbol, timeframe)
        signal, strategy_confidence = await self._generate_signal(analysis)
        agent_confidence = self._calculate_confidence(analysis, signal)
        # Blend: strategy's own quality assessment (60%) + agent's market context (40%)
        if strategy_confidence is not None and signal.get("action") != "HOLD":
            confidence = round(
                max(0.10, min(0.95, 0.6 * strategy_confidence + 0.4 * agent_confidence)), 4
            )
        else:
            confidence = agent_confidence

        decision = {
            "task": task,
            "analysis": self._sanitize_for_log(analysis),
            "signal": signal,
            "confidence": confidence,
            "reasoning": self._explain_reasoning(analysis, signal),
        }
        self.log_decision(decision)

        return {
            "success": True,
            "agent": self.agent_type,
            "signal": signal,
            "confidence": confidence,
            "analysis": self._sanitize_for_log(analysis),
        }

    # ------------------------------------------------------------------- analysis

    async def _analyze_market(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        """Fetch OHLCV and compute full technical analysis."""
        # Fallback if no exchange client is attached (unit tests)
        if self.exchange_client is None:
            logger.warning("No exchange client — returning minimal stub analysis")
            return self._stub_analysis(symbol, timeframe)

        try:
            ohlcv = await self.exchange_client.fetch_ohlcv(symbol, timeframe, limit=200)
        except Exception as exc:
            logger.error("Failed to fetch OHLCV for %s %s: %s", symbol, timeframe, exc)
            return self._stub_analysis(symbol, timeframe)

        if len(ohlcv) < TechnicalAnalyzer.MIN_CANDLES:
            logger.warning("Insufficient OHLCV data (%d candles)", len(ohlcv))
            return self._stub_analysis(symbol, timeframe)

        # 1. Technical indicators
        analyzer = TechnicalAnalyzer(ohlcv)
        indicators = analyzer.get_latest()

        # 2. Support / Resistance + Fibonacci
        sr_levels = self._sr_detector.detect(ohlcv)
        current_price = indicators.current_price or float(ohlcv[-1][4])
        fib_levels: Dict[str, float] = {}
        if sr_levels.support and sr_levels.resistance:
            fib_levels = SupportResistanceDetector.fibonacci_levels(
                sr_levels.support, sr_levels.resistance
            )

        # 3. Volume Profile
        vp_result = VolumeProfile(ohlcv).analyze()

        # 4. Regime detection
        regime = detect_regime(
            ema_fast=indicators.ema_fast,
            ema_slow=indicators.ema_slow,
            atr=indicators.atr,
            current_price=current_price,
        )
        eligible_strategies = strategies_for_regime(regime)

        # 5. Divergence
        rsi_series = analyzer.get_series("rsi")
        macd_hist_series = analyzer.get_series("macd_hist")
        rsi_div = self._div_detector.check_rsi_price(ohlcv, rsi_series)
        macd_div = self._div_detector.check_macd_price(ohlcv, macd_hist_series)

        # 6. Market extreme detection
        market_extreme = detect_market_extreme(
            rsi=indicators.rsi, volume_ratio=indicators.volume_ratio
        )

        # 7. Trend direction (single-timeframe, fast path)
        trend = None
        if indicators.ema_fast and indicators.ema_slow:
            trend = "bullish" if indicators.ema_fast > indicators.ema_slow else "bearish"

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "current_price": current_price,
            "trend": trend,
            "regime": regime,
            "eligible_strategies": eligible_strategies,
            "indicators": indicators,
            "support_resistance": sr_levels,
            "fibonacci_levels": fib_levels,
            "volume_profile": vp_result,
            "rsi_divergence": rsi_div,
            "macd_divergence": macd_div,
            "market_extreme": market_extreme,
            "_ohlcv": ohlcv,   # kept for strategy access, stripped before logging
        }

    # ------------------------------------------------------------------- signal

    async def _generate_signal(
        self, analysis: Dict[str, Any]
    ) -> tuple[Dict[str, Any], Optional[float]]:
        """Delegate signal generation to the appropriate strategy.

        Returns (signal_dict, strategy_raw_confidence).
        The strategy_raw_confidence is the strategy's own quality estimate (0-1) and
        is blended with the agent's analytical confidence in execute().
        """
        eligible = analysis.get("eligible_strategies", [])
        regime = analysis.get("regime", "unknown")
        _hold = {
            "action": "HOLD",
            "entry_price": analysis.get("current_price", 0.0),
            "stop_loss": None,
            "take_profit": None,
            "position_size_pct": 0.0,
        }

        if not eligible:
            return {**_hold, "reason": f"No strategy eligible for regime '{regime}'"}, None

        strategy_key = eligible[0]
        strategy = self._get_strategy(strategy_key)
        if strategy is None:
            return {**_hold, "reason": f"Strategy '{strategy_key}' could not be loaded"}, None

        market_data = self._build_market_data(analysis)
        result = await strategy.analyze(market_data)

        action_map = {"DCA_ENTRY": "BUY", "buy": "BUY", "sell": "SELL", "hold": "HOLD"}
        action = action_map.get(result.get("action", "hold"), "HOLD")
        strategy_confidence = result.get("confidence")

        # Unwrap nested signal dict (DCA wraps its signal) or use result directly
        signal_data = result.get("signal") or result

        ind = analysis.get("indicators")
        signal = {
            "action": action,
            "entry_price": analysis.get("current_price", 0.0),
            "stop_loss": signal_data.get("stop_loss") if isinstance(signal_data, dict) else None,
            "take_profit": signal_data.get("take_profit") if isinstance(signal_data, dict) else None,
            # Use per-order position size (not total across all DCA entries)
            "position_size_pct": signal_data.get("position_size_pct", 2.0)
            if isinstance(signal_data, dict)
            else 2.0,
            "strategy": strategy_key,
            "regime": regime,
            # Market context forwarded to guardrails for condition checks.
            "market_context": {
                "atr": ind.atr if ind else None,
                "bb_middle": ind.bb_middle if ind else None,
                "volume_ratio": ind.volume_ratio if ind else None,
            } if ind else None,
        }
        return signal, strategy_confidence

    # ---------------------------------------------------------------- confidence

    def _calculate_confidence(
        self, analysis: Dict[str, Any], signal: Dict[str, Any]
    ) -> float:
        """Multi-factor confidence score.

        Weights (sum = 1.0):
          trend_alignment      0.25
          indicator_confluence 0.30
          sr_proximity         0.20
          volume_confirmation  0.15
          divergence_bonus     0.10
        """
        score = 0.0
        indicators = analysis.get("indicators")
        if indicators is None:
            return 0.5

        action = signal.get("action", "HOLD")
        trend = analysis.get("trend")

        # Trend alignment
        if action == "BUY" and trend == "bullish":
            score += 0.25
        elif action == "SELL" and trend == "bearish":
            score += 0.25
        elif action == "HOLD":
            score += 0.10   # partial credit for cautious decision

        # Indicator confluence
        rsi = indicators.rsi
        macd_h = indicators.macd_hist
        bb_pct = indicators.bb_percent
        volume_ratio = indicators.volume_ratio

        indicator_hits = 0
        if rsi is not None:
            if action == "BUY" and rsi < 55:
                indicator_hits += 1
            elif action == "SELL" and rsi > 45:
                indicator_hits += 1
        if macd_h is not None:
            if action == "BUY" and macd_h > 0:
                indicator_hits += 1
            elif action == "SELL" and macd_h < 0:
                indicator_hits += 1
        if bb_pct is not None:
            if action == "BUY" and bb_pct < 0.3:
                indicator_hits += 1
            elif action == "SELL" and bb_pct > 0.7:
                indicator_hits += 1
        score += min(indicator_hits / 3, 1.0) * 0.30

        # S/R proximity
        sr = analysis.get("support_resistance")
        entry = signal.get("entry_price", 0.0)
        if sr and entry and sr.support and sr.resistance:
            sr_range = sr.resistance - sr.support
            if sr_range > 0:
                if action == "BUY":
                    proximity = 1.0 - (entry - sr.support) / sr_range
                    score += max(0.0, proximity) * 0.20
                elif action == "SELL":
                    proximity = (entry - sr.support) / sr_range
                    score += max(0.0, min(proximity, 1.0)) * 0.20

        # Volume confirmation
        if volume_ratio is not None and volume_ratio > 1.2:
            score += 0.15
        elif volume_ratio is not None and volume_ratio > 0.8:
            score += 0.07

        # Divergence bonus
        rsi_div = analysis.get("rsi_divergence")
        macd_div = analysis.get("macd_divergence")
        if rsi_div and rsi_div.detected:
            if action == "BUY" and rsi_div.kind == "bullish_divergence":
                score += 0.10
            elif action == "SELL" and rsi_div.kind == "bearish_divergence":
                score += 0.10
        elif macd_div and macd_div.detected:
            if action == "BUY" and macd_div.kind == "bullish_divergence":
                score += 0.05
            elif action == "SELL" and macd_div.kind == "bearish_divergence":
                score += 0.05

        return round(max(0.10, min(0.95, score)), 4)

    # ------------------------------------------------------------------ helpers

    def _build_market_data(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Build the market_data dict that strategies expect."""
        ind = analysis.get("indicators")
        ohlcv = analysis.get("_ohlcv", [])
        vp = analysis.get("volume_profile")
        return {
            "symbol": analysis.get("symbol"),
            "current_price": analysis.get("current_price", 0.0),
            "trend": analysis.get("trend"),
            "regime": analysis.get("regime"),
            # Flat indicator values for DCA / legacy strategies (0 fallback for None)
            "rsi": ind.rsi if (ind and ind.rsi is not None) else 50,
            "macd_histogram": ind.macd_hist if (ind and ind.macd_hist is not None) else 0,
            "at_bollinger_lower": (
                ind.bb_percent is not None and ind.bb_percent < 0.05
            ) if ind else False,
            "ma_20": ind.sma_20 if (ind and ind.sma_20 is not None) else 0,
            "ma_50": ind.sma_50 if (ind and ind.sma_50 is not None) else 0,
            "volume_24h": float(ohlcv[-1][5]) if ohlcv else 0,
            "avg_volume": float(ohlcv[-1][5]) / max(ind.volume_ratio, 0.001)
            if (ind and ind.volume_ratio and ohlcv)
            else 1,
            # Rich objects for advanced strategies
            "indicators": ind,
            "support_resistance": analysis.get("support_resistance"),
            "volume_profile": vp,
            "_raw_ohlcv": ohlcv,
        }

    def _get_strategy(self, key: str) -> Optional[Any]:
        """Lazily load and cache a strategy instance."""
        if key in self._strategy_cache:
            return self._strategy_cache[key]
        try:
            from src.strategies import STRATEGY_REGISTRY
            cls = STRATEGY_REGISTRY.get(key)
            if cls is None:
                logger.warning("Strategy key '%s' not found in registry", key)
                return None
            instance = cls()
            self._strategy_cache[key] = instance
            return instance
        except Exception as exc:
            logger.error("Failed to load strategy '%s': %s", key, exc)
            return None

    @staticmethod
    def _stub_analysis(symbol: str, timeframe: str) -> Dict[str, Any]:
        """Minimal analysis when exchange data is unavailable."""
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "current_price": 0.0,
            "trend": None,
            "regime": "unknown",
            "eligible_strategies": ["dca"],
            "indicators": None,
            "support_resistance": None,
            "fibonacci_levels": {},
            "volume_profile": None,
            "rsi_divergence": None,
            "macd_divergence": None,
            "market_extreme": None,
            "_ohlcv": [],
        }

    @staticmethod
    def _sanitize_for_log(analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Remove large objects before logging."""
        sanitized = dict(analysis)
        sanitized.pop("_ohlcv", None)
        # Convert dataclasses to dicts for JSON serialization
        for key in ("indicators", "support_resistance", "volume_profile",
                    "rsi_divergence", "macd_divergence"):
            val = sanitized.get(key)
            if val is not None and hasattr(val, "__dataclass_fields__"):
                from dataclasses import asdict
                sanitized[key] = asdict(val)
        return sanitized

    def _explain_reasoning(
        self, analysis: Dict[str, Any], signal: Dict[str, Any]
    ) -> str:
        ind = analysis.get("indicators")
        regime = analysis.get("regime", "unknown")
        action = signal.get("action", "HOLD")
        parts = [f"Regime: {regime}", f"Action: {action}"]
        if ind:
            if ind.rsi is not None:
                parts.append(f"RSI={ind.rsi:.1f}")
            if ind.macd_hist is not None:
                parts.append(f"MACD_hist={ind.macd_hist:.4f}")
            if ind.bb_percent is not None:
                parts.append(f"BB%={ind.bb_percent:.2f}")
        if analysis.get("market_extreme"):
            parts.append(f"ALERT: {analysis['market_extreme']}")
        return " | ".join(parts)
