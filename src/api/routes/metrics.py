"""GET /v1/metrics — portfolio KPIs computed from the ledger.

Trade-off: metrics are computed on demand from the append-only ledger. For the
current data volumes this is fast and always fresh; a cache table can be added
later if the ledger grows large (documented in the architecture plan).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_metrics_calculator
from src.api.schemas import APIResponse, Links, PortfolioMetricsOut
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
