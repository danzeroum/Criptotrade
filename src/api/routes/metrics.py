"""GET /v1/metrics — portfolio KPIs computed from the ledger.

Trade-off: metrics are computed on demand from the append-only ledger. For the
current data volumes this is fast and always fresh; a cache table can be added
later if the ledger grows large (documented in the architecture plan).
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_ledger, get_metrics_calculator
from src.api.schemas import APIResponse, EquityPoint, Links, PortfolioMetricsOut
from src.core.ledger import TradingLedger
from src.core.metrics import PortfolioMetricsCalculator

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get(
    "",
    response_model=APIResponse[PortfolioMetricsOut],
    summary="KPIs do portfólio (Sharpe, Win Rate, Max Drawdown, ...)",
)
async def get_metrics(
    period: str = Query("7d", pattern="^(1d|7d|30d|90d|all)$"),
    calc: PortfolioMetricsCalculator = Depends(get_metrics_calculator),
) -> APIResponse[PortfolioMetricsOut]:
    metrics = calc.compute(period=period)
    return APIResponse(
        data=PortfolioMetricsOut(**metrics.to_dict()),
        links=Links(
            self=f"/v1/metrics?period={period}",
            related={"alerts": "/v1/alerts/history", "hitl": "/v1/hitl/config"},
        ),
    )


@router.get(
    "/equity",
    response_model=APIResponse[List[EquityPoint]],
    summary="Série temporal de capital e drawdown (derivada do ledger)",
)
async def get_equity(
    period: str = Query("90d", pattern="^(7d|30d|90d|all)$"),
    ledger: TradingLedger = Depends(get_ledger),
    calc: PortfolioMetricsCalculator = Depends(get_metrics_calculator),
) -> APIResponse[List[EquityPoint]]:
    entries = [
        e for e in ledger.read_all()
        if e.get("event_type") == "position_closed"
    ]
    initial_capital = calc.initial_capital
    equity = initial_capital
    peak = equity
    points: List[EquityPoint] = []

    for e in entries:
        data = e.get("data", {})
        pnl = data.get("pnl", 0.0)
        ts = data.get("timestamp") or e.get("timestamp", "")
        equity += pnl
        peak = max(peak, equity)
        dd = (equity - peak) / peak * 100 if peak > 0 else 0.0
        points.append(EquityPoint(t=ts, equity=round(equity, 2), drawdown=round(dd, 4)))

    if not points:
        points = [EquityPoint(t="now", equity=initial_capital, drawdown=0.0)]

    return APIResponse(data=points)
