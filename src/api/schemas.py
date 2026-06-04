"""Pydantic v2 schemas for the API (envelope + outputs).

Conventions (validated against the repo's pydantic==2.6):
* Every response is wrapped in :class:`APIResponse` — never a bare object.
* ``_links`` (HATEOAS) is exposed via a field alias; FastAPI serialises by alias.
* Ratio fields that may be unknown are ``Optional`` (``None`` == "no data").
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Meta(BaseModel):
    total: int
    page: int = 1
    per_page: int = 20
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Links(BaseModel):
    self: str
    related: Optional[dict] = None


class APIResponse(BaseModel, Generic[T]):
    """Standard envelope for all successful responses."""

    model_config = ConfigDict(populate_by_name=True)

    data: T
    meta: Optional[Meta] = None
    links: Optional[Links] = Field(default=None, alias="_links")


class ErrorResponse(BaseModel):
    error: str
    message: str
    field: Optional[str] = None
    docs: str = "/v1/docs"


# ----------------------------------------------------------------- metrics
class PortfolioMetricsOut(BaseModel):
    sharpe_ratio: Optional[float]
    win_rate: Optional[float]
    max_drawdown: float
    profit_factor: Optional[float]
    total_trades: int
    open_positions: int
    portfolio_value_usdt: float
    pnl_period_usdt: float
    pnl_period_pct: float
    exposure_pct: float
    initial_capital_usdt: float
    period: str
    calculated_at: str
    has_data: bool


# ----------------------------------------------------------------- hitl
class AutonomyLevelOut(BaseModel):
    level: int
    threshold_usdt: float
    description: str


class HITLConfigOut(BaseModel):
    current_level: int
    threshold_usdt: float
    level_description: str
    min_level: int
    max_level: int
    pending_orders_count: int
    human_approved_today: int
    human_rejected_today: int
    last_changed_at: Optional[str] = None
    last_changed_by: Optional[str] = None
    levels: List[AutonomyLevelOut]


class AutonomyLevelPatch(BaseModel):
    level: int = Field(..., ge=0, le=3, description="Novo nível de autonomia (0-3)")
    reason: str = Field(..., min_length=5, description="Motivo da mudança de nível")
    operator: str = Field(default="operator", description="Quem alterou o nível")


# ----------------------------------------------------------------- alerts
class AlertOut(BaseModel):
    id: str
    severity: str
    type: str
    message: str
    agent_id: Optional[str] = None
    pair: Optional[str] = None
    auto_action: Optional[str] = None
    occurred_at: str


__all__ = [
    "APIResponse",
    "Meta",
    "Links",
    "ErrorResponse",
    "PortfolioMetricsOut",
    "AutonomyLevelOut",
    "HITLConfigOut",
    "AutonomyLevelPatch",
    "AlertOut",
]
