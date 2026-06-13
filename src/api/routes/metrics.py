"""GET /v1/metrics — portfolio KPIs computed from the ledger.

Trade-off: metrics are computed on demand from the append-only ledger. For the
current data volumes this is fast and always fresh; a cache table can be added
later if the ledger grows large (documented in the architecture plan).
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_ledger, get_metrics_calculator
from src.api.schemas import APIResponse, EquityPoint, Links, PortfolioMetricsOut
from src.core.ledger import TradingLedger
from src.core.metrics import PortfolioMetricsCalculator
from src.core.pairs import allowed_pairs, is_allowed

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _validated_symbol(symbol: Optional[str]) -> Optional[str]:
    """Normalize + allowlist-check an optional ``?symbol`` filter (None = all pairs)."""
    if symbol is None or not symbol.strip():
        return None
    sym = symbol.replace("-", "/").upper() if "/" not in symbol else symbol.upper()
    if not is_allowed(sym):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_pair",
                "message": f"Par '{sym}' não permitido.",
                "valid": allowed_pairs(),
                "docs": "/v1/docs",
            },
        )
    return sym


@router.get(
    "",
    response_model=APIResponse[PortfolioMetricsOut],
    summary="KPIs do portfólio (Sharpe, Win Rate, Max Drawdown, ...)",
)
async def get_metrics(
    period: str = Query("7d", pattern="^(1d|7d|30d|90d|all)$"),
    symbol: Optional[str] = Query(None, description="Filtrar por par (ex.: BTC/USDT). Vazio = portfólio inteiro."),
    calc: PortfolioMetricsCalculator = Depends(get_metrics_calculator),
) -> APIResponse[PortfolioMetricsOut]:
    sym = _validated_symbol(symbol)
    metrics = calc.compute(period=period, symbol=sym)
    self_link = f"/v1/metrics?period={period}" + (f"&symbol={sym}" if sym else "")
    return APIResponse(
        data=PortfolioMetricsOut(**metrics.to_dict()),
        links=Links(
            self=self_link,
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
    symbol: Optional[str] = Query(None, description="Filtrar por par (ex.: BTC/USDT). Vazio = portfólio inteiro."),
    ledger: TradingLedger = Depends(get_ledger),
    calc: PortfolioMetricsCalculator = Depends(get_metrics_calculator),
) -> APIResponse[List[EquityPoint]]:
    sym = _validated_symbol(symbol)
    entries = [
        e for e in ledger.read_all()
        if e.get("event_type") == "position_closed"
        and (sym is None or str(e.get("data", {}).get("symbol", "")).upper() == sym)
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
