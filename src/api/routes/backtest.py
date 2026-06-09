"""/v1/backtest — expõe os engines de backtest via REST com padrão de job assíncrono.

POST /run → retorna job_id + status "running"; UI faz polling em GET /jobs/{id}.
POST /montecarlo e /walkforward são síncronos (rápidos).
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, HTTPException

from src.api.deps import get_exchange_client, get_metrics_calculator
from src.api.schemas import (
    APIResponse,
    BacktestConfigIn,
    BacktestJobOut,
    BacktestResultOut,
    EquityPoint,
    MonteCarloOut,
    WalkForwardFold,
    WalkForwardOut,
)
from src.backtest.engine import BacktestEngine, BacktestResult
from src.backtest.monte_carlo import MonteCarloSimulator
from src.backtest.validator import WalkForwardValidator
from src.core.exchange_client import ExchangeClient
from src.core.metrics import PortfolioMetricsCalculator

router = APIRouter(prefix="/backtest", tags=["backtest"])

_jobs: Dict[str, Dict[str, Any]] = {}


class _SimpleStrategy:
    """Minimal strategy adapter for the backtest engine — RSI + MACD signal."""

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        indicators = market_data.get("indicators", {})
        rsi = indicators.get("rsi", 50)
        macd_hist = indicators.get("macd_hist", 0)
        price = market_data.get("current_price", 0)
        atr = indicators.get("atr", price * 0.02 if price else 0)

        if rsi < 30 and macd_hist > 0:
            return {
                "action": "buy",
                "position_size_pct": 2.0,
                "stop_loss": price - atr * 1.5,
                "take_profit": price + atr * 3.0,
            }
        if rsi > 70 and macd_hist < 0:
            return {
                "action": "sell",
                "position_size_pct": 2.0,
                "stop_loss": price + atr * 1.5,
                "take_profit": price - atr * 3.0,
            }
        return {"action": "hold"}


def _result_to_out(result: BacktestResult, initial_capital: float) -> BacktestResultOut:
    trades = result.trades or []
    equity: List[EquityPoint] = []
    cap = initial_capital
    peak = cap
    for i, t in enumerate(trades):
        cap += t.pnl_usdt
        peak = max(peak, cap)
        dd = (cap - peak) / peak * 100 if peak > 0 else 0.0
        equity.append(EquityPoint(
            t=f"trade_{i}",
            equity=round(cap, 2),
            drawdown=round(dd, 4),
        ))

    return BacktestResultOut(
        total_trades=result.total_trades,
        win_rate=round(result.win_rate, 4),
        pnl_pct=round(result.total_pnl_pct * 100, 4),
        pnl_usdt=round(result.total_pnl_usdt, 2),
        max_drawdown=round(result.max_drawdown_pct, 4),
        sharpe=round(result.sharpe_ratio, 4) if result.sharpe_ratio is not None else None,
        profit_factor=round(result.profit_factor, 4) if result.profit_factor is not None else None,
        avg_win_pct=round(result.avg_win_pct, 4),
        avg_loss_pct=round(result.avg_loss_pct, 4),
        expectancy=round(result.expectancy, 2),
        equity=equity,
    )


async def _run_job(job_id: str, config: BacktestConfigIn, client: ExchangeClient, initial_capital: float) -> None:
    try:
        ohlcv = await client.fetch_ohlcv("BTC/USDT", timeframe="1h", limit=500)
        engine = BacktestEngine(
            initial_capital=initial_capital,
            commission_pct=config.commission_pct / 100,
            slippage_bps=config.slippage_bps,
        )
        result = await engine.run(_SimpleStrategy(), ohlcv)
        _jobs[job_id] = {
            "status": "done",
            "result": _result_to_out(result, initial_capital),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        _jobs[job_id] = {"status": "error", "error": str(exc)}


@router.post(
    "/run",
    response_model=APIResponse[BacktestJobOut],
    summary="Inicia um backtest assíncrono; retorna job_id para polling",
    status_code=202,
)
async def run_backtest(
    config: BacktestConfigIn = Body(...),
    client: ExchangeClient = Depends(get_exchange_client),
    calc: PortfolioMetricsCalculator = Depends(get_metrics_calculator),
) -> APIResponse[BacktestJobOut]:
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    _jobs[job_id] = {"status": "running"}
    asyncio.create_task(_run_job(job_id, config, client, calc.initial_capital))
    return APIResponse(data=BacktestJobOut(job_id=job_id, status="running"))


@router.get(
    "/jobs/{job_id}",
    response_model=APIResponse[BacktestJobOut],
    summary="Polling do resultado de um job de backtest",
)
async def get_job(job_id: str) -> APIResponse[BacktestJobOut]:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": "job_not_found", "message": f"Job '{job_id}' não encontrado"})
    return APIResponse(data=BacktestJobOut(
        job_id=job_id,
        status=job["status"],
        result=job.get("result"),
        error=job.get("error"),
    ))


@router.post(
    "/montecarlo",
    response_model=APIResponse[MonteCarloOut],
    summary="Simulação de Monte Carlo sobre os trades do histórico",
)
async def run_montecarlo(
    config: BacktestConfigIn = Body(...),
    client: ExchangeClient = Depends(get_exchange_client),
    calc: PortfolioMetricsCalculator = Depends(get_metrics_calculator),
) -> APIResponse[MonteCarloOut]:
    ohlcv = await client.fetch_ohlcv("BTC/USDT", timeframe="1h", limit=500)
    engine = BacktestEngine(
        initial_capital=calc.initial_capital,
        commission_pct=config.commission_pct / 100,
        slippage_bps=config.slippage_bps,
    )
    result = await engine.run(_SimpleStrategy(), ohlcv)
    pnl_pcts = [t.pnl_pct * 100 for t in result.trades] if result.trades else [0.0]

    mc = MonteCarloSimulator(n_simulations=config.monte_carlo_sims)
    mc_result = mc.simulate(pnl_pcts)

    hist, _ = _build_histogram(pnl_pcts, bins=20)
    return APIResponse(data=MonteCarloOut(
        n=mc_result.n_simulations,
        p5=round(mc_result.percentile_5_pnl_pct, 4),
        p50=round(mc_result.median_final_pnl_pct, 4),
        p95=round(mc_result.percentile_95_pnl_pct, 4),
        profitable_pct=round(mc_result.pct_profitable, 4),
        rejected=mc_result.rejected,
        histogram=hist,
        max_simulated_drawdown=round(mc_result.max_simulated_drawdown, 4),
    ))


@router.post(
    "/walkforward",
    response_model=APIResponse[WalkForwardOut],
    summary="Walk-forward validation — detecta overfitting",
)
async def run_walkforward(
    config: BacktestConfigIn = Body(...),
    client: ExchangeClient = Depends(get_exchange_client),
    calc: PortfolioMetricsCalculator = Depends(get_metrics_calculator),
) -> APIResponse[WalkForwardOut]:
    ohlcv = await client.fetch_ohlcv("BTC/USDT", timeframe="1h", limit=500)
    validator = WalkForwardValidator(
        window_size=200,
        test_size=50,
        min_windows=2,
        initial_capital=calc.initial_capital,
    )
    wf = await validator.validate(_SimpleStrategy(), ohlcv)

    folds = [
        WalkForwardFold(
            window_index=w.window_index,
            train_sharpe=round(w.train_result.sharpe_ratio, 4) if w.train_result.sharpe_ratio else None,
            test_sharpe=round(w.test_result.sharpe_ratio, 4) if w.test_result.sharpe_ratio else None,
            train_pnl_pct=round(w.train_result.total_pnl_pct * 100, 4),
            test_pnl_pct=round(w.test_result.total_pnl_pct * 100, 4),
        )
        for w in (wf.window_results or [])
    ]

    return APIResponse(data=WalkForwardOut(
        valid=wf.valid,
        windows=wf.n_windows,
        sharpe_deviation=round(wf.sharpe_deviation, 4) if wf.sharpe_deviation is not None else None,
        folds=folds,
    ))


def _build_histogram(values: List[float], bins: int = 20):
    if not values:
        return [], []
    lo, hi = min(values), max(values)
    if lo == hi:
        return [len(values)] + [0] * (bins - 1), [lo]
    width = (hi - lo) / bins
    counts = [0] * bins
    edges = [lo + i * width for i in range(bins)]
    for v in values:
        idx = min(int((v - lo) / width), bins - 1)
        counts[idx] += 1
    return counts, edges
