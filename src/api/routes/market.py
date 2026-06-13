"""/v1/market/{pair} — exposes src/analysis/* over REST.

All endpoints accept the pair as a URL-encoded path segment, e.g. BTC%2FUSDT.
Candles are fetched from ExchangeClient (dry-run = synthetic, live = CCXT).
"""
from __future__ import annotations

import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_exchange_client
from src.core.pairs import allowed_pairs
from src.api.schemas import (
    APIResponse,
    CandleOut,
    ConfidenceFactor,
    IndicatorsOut,
    LevelsOut,
    MacdOut,
    BollingerOut,
    StochOut,
    PatternOut,
    RegimeOut,
    SRLevelOut,
    SignalOut,
    TickerOut,
    VolumeProfileBin,
    VolumeProfileOut,
)
router = APIRouter(prefix="/market", tags=["market"])

# Timeframe → duration in seconds (for signal validity windows).
_TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}


def _as_of(ohlcv: list) -> datetime:
    """Freshness anchor: the close time of the latest candle (UTC), not the wall clock.

    "Stale" should reflect market-data age, so the UI counts from the last candle.
    """
    if ohlcv:
        return datetime.fromtimestamp(ohlcv[-1][0] / 1000, tz=timezone.utc)
    return datetime.now(timezone.utc)


def _regime_history(analyzer: Any, ohlcv: list, current_regime: str, cap: int = 200):
    """How long the current regime has held + what it transitioned from (M11).

    Stateless and cheap: re-applies ``detect_regime`` over the already-computed
    EMA/ATR series (no re-fit, no extra exchange fetch). Walks backward from the
    latest candle, capped at ``cap`` bars, and stops at the first transition.

    Returns ``(bars_in_regime, since_dt, last_transition)``.
    """
    from src.analysis.regime_detector import detect_regime  # lazy

    ema_f = analyzer.get_series("ema_fast")
    ema_s = analyzer.get_series("ema_slow")
    atr_s = analyzer.get_series("atr")
    close_s = analyzer.get_series("close")
    n = min(len(close_s), len(ohlcv))

    def _at(series: Any, i: int):
        try:
            v = float(series.iloc[i])
            return None if v != v else v  # NaN -> None
        except (IndexError, TypeError, ValueError):
            return None

    bars = 0
    since_ms = ohlcv[0][0] if ohlcv else None
    transition = None
    for i in range(n - 1, max(-1, n - 1 - cap), -1):
        r = detect_regime(
            ema_fast=_at(ema_f, i), ema_slow=_at(ema_s, i),
            atr=_at(atr_s, i), current_price=_at(close_s, i),
        )
        if r == current_regime:
            bars += 1
            since_ms = ohlcv[i][0]
        else:
            transition = f"{r}→{current_regime}"
            break

    since_dt = (
        datetime.fromtimestamp(since_ms / 1000, tz=timezone.utc) if since_ms else None
    )
    return bars, since_dt, transition


# Computed at import (re-evaluated on importlib.reload, which the tests use to
# pick up a changed MARKET_PAIRS). Single source of truth lives in core.pairs.
_ALLOWED_PAIRS: frozenset[str] = frozenset(allowed_pairs())

_REGIME_LABELS = {
    "strong_uptrend": "Alta forte",
    "strong_downtrend": "Baixa forte",
    "sideways": "Lateral",
    "chaotic": "Caótico",
    "unknown": "Desconhecido",
}


def _decode_pair(raw: str) -> str:
    decoded = urllib.parse.unquote(raw)
    # Accept "BTC-USDT" (dash) as well as "BTC/USDT" (slash or %2F)
    symbol = decoded.replace("-", "/") if "/" not in decoded else decoded
    symbol = symbol.upper()
    if symbol not in _ALLOWED_PAIRS:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_pair",
                "message": f"Par '{symbol}' não permitido. Use um dos pares configurados.",
                "valid": sorted(_ALLOWED_PAIRS),
                "docs": "/v1/docs",
            },
        )
    return symbol


@router.get(
    "/pairs",
    response_model=APIResponse[List[str]],
    summary="Pares permitidos (allowlist MARKET_PAIRS) — alimenta o seletor da UI",
)
async def get_pairs() -> APIResponse[List[str]]:
    # Same source _decode_pair validates against, so the dropdown can only offer
    # pairs the other endpoints accept.
    return APIResponse(data=sorted(_ALLOWED_PAIRS))


async def _fetch_candles(pair: str, tf: str, limit: int, client: Any) -> list:
    try:
        return await client.fetch_ohlcv(pair, timeframe=tf, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail={
            "error": "market_data_unavailable",
            "message": f"Não foi possível obter candles para {pair}: {exc}",
        }) from exc


@router.get(
    "/{pair}/candles",
    response_model=APIResponse[List[CandleOut]],
    summary="OHLCV candles para o par (dry-run = sintético)",
)
async def get_candles(
    pair: str,
    tf: str = Query("1h", pattern="^(1m|5m|15m|1h|4h|1d)$"),
    limit: int = Query(100, ge=10, le=500),
    client: Any = Depends(get_exchange_client),
) -> APIResponse[List[CandleOut]]:
    symbol = _decode_pair(pair)
    ohlcv = await _fetch_candles(symbol, tf, limit, client)
    candles = [CandleOut(t=int(r[0]), o=r[1], h=r[2], lo=r[3], c=r[4], v=r[5]) for r in ohlcv]
    return APIResponse(data=candles)


@router.get(
    "/{pair}/ticker",
    response_model=APIResponse[TickerOut],
    summary="Preço atual + variação 24h (derivado de OHLCV; dry-run = sintético)",
)
async def get_ticker(
    pair: str,
    client: Any = Depends(get_exchange_client),
) -> APIResponse[TickerOut]:
    symbol = _decode_pair(pair)
    # 25 hourly candles => ~24h ago reference + now. Works in dry-run and live.
    ohlcv = await _fetch_candles(symbol, "1h", 25, client)
    if not ohlcv:
        raise HTTPException(status_code=503, detail={
            "error": "market_data_unavailable",
            "message": f"Sem dados de mercado para {symbol}",
        })
    last = float(ohlcv[-1][4])
    ref = float(ohlcv[0][4])  # close ~24h ago
    change = ((last - ref) / ref * 100) if ref else 0.0
    return APIResponse(data=TickerOut(
        last=round(last, 8),
        change_24h_pct=round(change, 4),
        high_24h=round(max(float(c[2]) for c in ohlcv), 8),
        low_24h=round(min(float(c[3]) for c in ohlcv), 8),
    ))


@router.get(
    "/{pair}/indicators",
    response_model=APIResponse[IndicatorsOut],
    summary="Indicadores técnicos (RSI, MACD, BB, ATR, MAs, Stoch)",
)
async def get_indicators(
    pair: str,
    tf: str = Query("1h"),
    limit: int = Query(150, ge=50, le=500),
    client: Any = Depends(get_exchange_client),
) -> APIResponse[IndicatorsOut]:
    from src.analysis.indicators import TechnicalAnalyzer  # lazy — numpy optional in CI
    symbol = _decode_pair(pair)
    ohlcv = await _fetch_candles(symbol, tf, limit, client)
    try:
        analyzer = TechnicalAnalyzer(ohlcv)
        ind = analyzer.get_latest()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": "insufficient_data", "message": str(exc)}) from exc

    macd = MacdOut(
        macd=ind.macd_line or 0.0,
        signal=ind.macd_signal or 0.0,
        hist=ind.macd_hist or 0.0,
    ) if ind.macd_line is not None else None

    stoch = StochOut(k=ind.stochastic_k or 0.0, d=ind.stochastic_d or 0.0) \
        if ind.stochastic_k is not None else None

    bb = BollingerOut(
        up=ind.bb_upper or 0.0, mid=ind.bb_middle or 0.0,
        low=ind.bb_lower or 0.0, pct_b=ind.bb_percent or 0.0,
    ) if ind.bb_upper is not None else None

    price = ind.current_price or 0.0
    atr_pct = round((ind.atr / price) * 100, 4) if ind.atr and price else None

    obv_trend: int | None = None
    if ind.obv is not None:
        obv_series = analyzer.get_series("obv")
        if len(obv_series) >= 5:
            obv_trend = 1 if float(obv_series.iloc[-1]) > float(obv_series.iloc[-5]) else -1

    return APIResponse(data=IndicatorsOut(
        rsi=ind.rsi, macd=macd, stoch=stoch, bb=bb,
        atr=ind.atr, atr_pct=atr_pct,
        ema9=ind.ema_fast, ema21=ind.ema_slow,
        sma20=ind.sma_20, sma50=ind.sma_50, sma200=ind.sma_200,
        obv_trend=obv_trend, volume_ratio=ind.volume_ratio,
        current_price=ind.current_price,
        as_of=_as_of(ohlcv),
    ))


@router.get(
    "/{pair}/regime",
    response_model=APIResponse[RegimeOut],
    summary="Regime de mercado atual (sideways | uptrend | downtrend | chaotic)",
)
async def get_regime(
    pair: str,
    tf: str = Query("1h"),
    limit: int = Query(150, ge=50, le=500),
    client: Any = Depends(get_exchange_client),
) -> APIResponse[RegimeOut]:
    from src.analysis.indicators import TechnicalAnalyzer  # lazy — numpy optional in CI
    from src.analysis.regime_detector import (  # lazy
        detect_market_extreme,
        detect_regime,
        strategies_for_regime,
    )
    symbol = _decode_pair(pair)
    ohlcv = await _fetch_candles(symbol, tf, limit, client)
    try:
        analyzer = TechnicalAnalyzer(ohlcv)
        ind = analyzer.get_latest()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": "insufficient_data", "message": str(exc)}) from exc

    regime = detect_regime(
        ema_fast=ind.ema_fast, ema_slow=ind.ema_slow,
        atr=ind.atr, current_price=ind.current_price,
    )
    strategies = strategies_for_regime(regime)

    ema_spread = abs((ind.ema_fast or 0) - (ind.ema_slow or 0)) / (ind.current_price or 1)
    confidence = min(1.0, round(ema_spread * 20, 2)) if regime not in ("unknown", "chaotic") else 0.5

    # M11: temporal context (duration + last transition) and euphoria/panic flag.
    bars_in_regime, since_dt, last_transition = _regime_history(analyzer, ohlcv, regime)
    extreme = detect_market_extreme(ind.rsi, ind.volume_ratio)

    return APIResponse(data=RegimeOut(
        regime=regime,
        confidence=confidence,
        label=_REGIME_LABELS.get(regime, regime),
        active_strategies=strategies,
        bars_in_regime=bars_in_regime,
        since=since_dt,
        last_transition=last_transition,
        extreme=extreme,
        as_of=_as_of(ohlcv),
    ))


@router.get(
    "/{pair}/levels",
    response_model=APIResponse[LevelsOut],
    summary="Suporte/Resistência e níveis de Fibonacci",
)
async def get_levels(
    pair: str,
    tf: str = Query("1h"),
    limit: int = Query(150, ge=50, le=500),
    client: Any = Depends(get_exchange_client),
) -> APIResponse[LevelsOut]:
    from src.analysis.support_resistance import SupportResistanceDetector  # lazy
    symbol = _decode_pair(pair)
    ohlcv = await _fetch_candles(symbol, tf, limit, client)

    detector = SupportResistanceDetector()
    sr = detector.detect(ohlcv)

    support_zones = [
        SRLevelOut(price=z.price, strength=z.strength)
        for z in sr.zones if z.kind == "support"
    ]
    resistance_zones = [
        SRLevelOut(price=z.price, strength=z.strength)
        for z in sr.zones if z.kind == "resistance"
    ]

    highs = [r[2] for r in ohlcv]
    lows = [r[3] for r in ohlcv]
    high = max(highs) if highs else 0.0
    low = min(lows) if lows else 0.0
    diff = high - low
    fib_ratios = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    fib_levels = [round(low + diff * r, 2) for r in fib_ratios] if diff > 0 else []

    return APIResponse(data=LevelsOut(
        support=sorted(support_zones, key=lambda x: x.price, reverse=True),
        resistance=sorted(resistance_zones, key=lambda x: x.price),
        fib=fib_levels,
    ))


@router.get(
    "/{pair}/volume-profile",
    response_model=APIResponse[VolumeProfileOut],
    summary="Volume Profile (POC, VAH, VAL, LVN)",
)
async def get_volume_profile(
    pair: str,
    tf: str = Query("1h"),
    limit: int = Query(150, ge=50, le=500),
    bins: int = Query(20, ge=10, le=50),
    client: Any = Depends(get_exchange_client),
) -> APIResponse[VolumeProfileOut]:
    from src.analysis.volume_profile import VolumeProfile  # lazy — numpy optional in CI
    symbol = _decode_pair(pair)
    ohlcv = await _fetch_candles(symbol, tf, limit, client)

    vp = VolumeProfile(ohlcv, price_bins=bins)
    result = vp.analyze()

    total_vol = sum(r[5] for r in ohlcv) or 1.0
    highs = [r[2] for r in ohlcv]
    lows = [r[3] for r in ohlcv]
    price_min = min(lows) if lows else 0.0
    price_max = max(highs) if highs else 0.0

    import numpy as np
    if price_max > price_min:
        edges = np.linspace(price_min, price_max, bins + 1)
        bin_vols = np.zeros(bins)
        for candle in ohlcv:
            lo, hi, vol = candle[3], candle[2], candle[5]
            for i in range(bins):
                overlap = min(hi, edges[i + 1]) - max(lo, edges[i])
                if overlap > 0 and (hi - lo) > 0:
                    bin_vols[i] += vol * (overlap / (hi - lo))
        bin_prices = [(edges[i] + edges[i + 1]) / 2 for i in range(bins)]
        out_bins = [
            VolumeProfileBin(
                price=round(float(bin_prices[i]), 2),
                volume=round(float(bin_vols[i]), 4),
                pct=round(float(bin_vols[i]) / total_vol * 100, 2),
            )
            for i in range(bins)
        ]
    else:
        out_bins = []

    return APIResponse(data=VolumeProfileOut(
        poc=result.poc,
        vah=result.value_area_high,
        val=result.value_area_low,
        lvn=result.low_volume_nodes,
        bins=out_bins,
    ))


@router.get(
    "/{pair}/patterns",
    response_model=APIResponse[List[PatternOut]],
    summary="Padrões gráficos detectados (H&S, Double Top/Bottom, Triangles)",
)
async def get_patterns(
    pair: str,
    tf: str = Query("1h"),
    limit: int = Query(150, ge=50, le=500),
    client: Any = Depends(get_exchange_client),
) -> APIResponse[List[PatternOut]]:
    from src.analysis.pattern_scanner import PatternScanner  # lazy — numpy optional in CI
    symbol = _decode_pair(pair)
    ohlcv = await _fetch_candles(symbol, tf, limit, client)

    scanner = PatternScanner()
    results = scanner.scan(ohlcv)

    patterns = [
        PatternOut(
            name=r.pattern,
            direction=r.direction,
            confidence=round(r.confidence, 3),
            target=r.target_price,
            description=r.description,
        )
        for r in results
    ]
    return APIResponse(data=patterns)


@router.get(
    "/{pair}/signal",
    response_model=APIResponse[SignalOut],
    summary="Sinal de trading atual (buy/sell/hold) baseado em indicadores",
)
async def get_signal(
    pair: str,
    tf: str = Query("1h"),
    limit: int = Query(150, ge=50, le=500),
    client: Any = Depends(get_exchange_client),
) -> APIResponse[SignalOut]:
    from src.analysis.indicators import TechnicalAnalyzer  # lazy — numpy optional in CI
    from src.analysis.regime_detector import detect_regime, strategies_for_regime  # lazy
    symbol = _decode_pair(pair)
    ohlcv = await _fetch_candles(symbol, tf, limit, client)
    try:
        analyzer = TechnicalAnalyzer(ohlcv)
        ind = analyzer.get_latest()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": "insufficient_data", "message": str(exc)}) from exc

    regime = detect_regime(
        ema_fast=ind.ema_fast, ema_slow=ind.ema_slow,
        atr=ind.atr, current_price=ind.current_price,
    )
    strategies = strategies_for_regime(regime)
    strategy = strategies[0] if strategies else "hold"

    price = ind.current_price or (ohlcv[-1][4] if ohlcv else 0.0)
    atr = ind.atr or (price * 0.02)
    rsi = ind.rsi or 50.0
    macd_hist = ind.macd_hist or 0.0

    buy_score = 0.0
    sell_score = 0.0
    reasons = []

    # Track each factor's directional contribution so we can expose a faithful
    # confidence breakdown (M6) without changing the aggregate math below.
    # direction: +1 favors buy, -1 favors sell, 0 neutral; pts = magnitude added.
    rsi_dir, rsi_pts, rsi_note = 0, 0.0, f"RSI neutro ({rsi:.0f})"
    if rsi < 30:
        buy_score += 0.4
        reasons.append("RSI sobrevendido")
        rsi_dir, rsi_pts, rsi_note = 1, 0.4, "RSI sobrevendido"
    elif rsi > 70:
        sell_score += 0.4
        reasons.append("RSI sobrecomprado")
        rsi_dir, rsi_pts, rsi_note = -1, 0.4, "RSI sobrecomprado"

    macd_dir, macd_pts, macd_note = 0, 0.0, "MACD sem cruzamento"
    if macd_hist > 0 and (ind.macd_line or 0) > (ind.macd_signal or 0):
        buy_score += 0.3
        reasons.append("MACD cruzamento bullish")
        macd_dir, macd_pts, macd_note = 1, 0.3, "MACD cruzamento bullish"
    elif macd_hist < 0 and (ind.macd_line or 0) < (ind.macd_signal or 0):
        sell_score += 0.3
        reasons.append("MACD cruzamento bearish")
        macd_dir, macd_pts, macd_note = -1, 0.3, "MACD cruzamento bearish"

    regime_dir, regime_pts, regime_note = 0, 0.0, f"Regime {regime}"
    if regime == "strong_uptrend":
        buy_score += 0.3
        regime_dir, regime_pts, regime_note = 1, 0.3, "Regime de alta forte"
    elif regime == "strong_downtrend":
        sell_score += 0.3
        regime_dir, regime_pts, regime_note = -1, 0.3, "Regime de baixa forte"
    elif regime == "chaotic":
        buy_score = sell_score = 0.0
        reasons = ["Regime caótico — sem sinal"]
        regime_dir, regime_pts, regime_note = 0, 0.0, "Regime caótico — sem sinal"

    if buy_score >= 0.4 and buy_score > sell_score and regime != "chaotic":
        action = "buy"
        confidence = min(0.95, round(buy_score, 2))
        stop = round(price - atr * 1.5, 2)
        tp = round(price + atr * 3.0, 2)
        rr = round((tp - price) / (price - stop), 2) if (price - stop) > 0 else None
    elif sell_score >= 0.4 and sell_score > buy_score and regime != "chaotic":
        action = "sell"
        confidence = min(0.95, round(sell_score, 2))
        stop = round(price + atr * 1.5, 2)
        tp = round(price - atr * 3.0, 2)
        rr = round((price - tp) / (stop - price), 2) if (stop - price) > 0 else None
    else:
        action = "hold"
        confidence = 0.3
        stop = None
        tp = None
        rr = None
        reasons = reasons or ["Sem confluência suficiente"]

    # Structure the factors that drove the score above (M6). Contribution is
    # signed toward the chosen action; for "hold" nothing contributes.
    def _factor(name: str, weight: float, direction: int, points: float, note: str) -> ConfidenceFactor:
        if action == "buy":
            contribution = points if direction == 1 else (-points if direction == -1 else 0.0)
        elif action == "sell":
            contribution = points if direction == -1 else (-points if direction == 1 else 0.0)
        else:
            contribution = 0.0
        score = round(max(0.0, contribution) / weight, 4) if weight else 0.0
        return ConfidenceFactor(
            name=name, weight=weight, score=score,
            contribution=round(contribution, 4), note=note,
        )

    confidence_factors = [
        _factor("RSI", 0.4, rsi_dir, rsi_pts, rsi_note),
        _factor("MACD", 0.3, macd_dir, macd_pts, macd_note),
        _factor("Regime", 0.3, regime_dir, regime_pts, regime_note),
    ]

    as_of = _as_of(ohlcv)
    valid_until = as_of + timedelta(seconds=_TF_SECONDS.get(tf, 3600))

    return APIResponse(data=SignalOut(
        action=action,
        entry=round(price, 2),
        stop=stop,
        take_profit=tp,
        position_size_pct=2.0,
        rr=rr,
        strategy=strategy,
        confidence=confidence,
        reason=", ".join(reasons) or "hold",
        confidence_factors=confidence_factors,
        valid_until=valid_until,
        as_of=as_of,
    ))
