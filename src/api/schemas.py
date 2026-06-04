"""Pydantic v2 schemas for the API (envelope + outputs).

Conventions (validated against the repo's pydantic==2.6):
* Every response is wrapped in :class:`APIResponse` — never a bare object.
* ``_links`` (HATEOAS) is exposed via a field alias; FastAPI serialises by alias.
* Ratio fields that may be unknown are ``Optional`` (``None`` == "no data").
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


# ----------------------------------------------------------------- orders
class OrderSide(str, Enum):
    buy = "buy"
    sell = "sell"


class OrderCreate(BaseModel):
    """Submit a new order. Validation makes it hard to use incorrectly."""

    pair: str = Field(..., pattern=r"^[A-Z]{2,10}/[A-Z]{2,10}$", examples=["BTC/USDT"])
    side: OrderSide
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0, description="Preço de referência/entrada (USDT)")
    strategy: str = Field(..., min_length=1)
    agent_id: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0, le=1)
    reason: str = Field(..., min_length=10)
    critical: bool = Field(default=False, description="Força aprovação humana mesmo se dentro do limite")
    # Risk fields — required for real guardrail validation (stop loss is mandatory).
    position_size_pct: float = Field(..., gt=0, le=100, description="% do portfólio na posição")
    stop_loss: float = Field(..., gt=0, description="Preço de stop loss (obrigatório)")
    take_profit: Optional[float] = Field(default=None, gt=0, description="Preço-alvo (opcional)")


class OrderDecisionPatch(BaseModel):
    """Operator decision on a pending order (the core HITL action)."""

    decision: str = Field(..., pattern="^(approve|reject)$")
    # validate_default ensures the cross-field check below runs even when the
    # client omits operator_note (otherwise Pydantic skips validation of defaults).
    operator_note: Optional[str] = Field(default=None, validate_default=True)
    operator: str = Field(default="operator")

    @field_validator("operator_note")
    @classmethod
    def note_required_on_reject(cls, v, info):
        if info.data.get("decision") == "reject" and not (v and v.strip()):
            raise ValueError("operator_note é obrigatório ao rejeitar uma ordem")
        return v


class OrderOut(BaseModel):
    id: str
    pair: str
    side: str
    quantity: float
    price: float
    notional: float
    status: str
    strategy: str
    agent_id: str
    confidence: float
    reason: str
    critical: bool
    auto_approved: bool
    operator_note: Optional[str] = None
    operator_id: Optional[str] = None
    created_at: str
    resolved_at: Optional[str] = None
    filled_at: Optional[str] = None


# ----------------------------------------------------------------- agents
class AgentStatusOut(BaseModel):
    id: str
    domain: str
    implemented: bool
    description: str
    status: str
    cycles: int
    last_action_at: Optional[str] = None


# ----------------------------------------------------------------- process log
class ProcessEventOut(BaseModel):
    case_id: str
    activity: str
    actor: str
    timestamp: str
    attributes: dict = Field(default_factory=dict)


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
    "OrderSide",
    "OrderCreate",
    "OrderDecisionPatch",
    "OrderOut",
    "AgentStatusOut",
    "ProcessEventOut",
    "AlertOut",
]
