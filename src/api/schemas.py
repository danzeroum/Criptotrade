"""Pydantic v2 schemas for the API (envelope + outputs).

Conventions (validated against the repo's pydantic==2.6):
* Every response is wrapped in :class:`APIResponse` — never a bare object.
* ``_links`` (HATEOAS) is exposed via a field alias; FastAPI serialises by alias.
* Ratio fields that may be unknown are ``Optional`` (``None`` == "no data").
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.core.pairs import is_allowed

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
    confirm: bool = Field(default=False, description="Obrigatório confirm=true para escalar para autonomia total (nível 3)")


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
    position_size_pct: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    rr: Optional[float] = None
    created_at: str
    resolved_at: Optional[str] = None
    filled_at: Optional[str] = None


# ----------------------------------------------------------------- closed trades
class ClosedTradeOut(BaseModel):
    order_id: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    fee: float = 0.0
    pnl: float
    pnl_pct: float
    opened_at: Optional[str] = None
    closed_at: Optional[str] = None


# ----------------------------------------------------------------- agents
class AgentStatusOut(BaseModel):
    id: str
    domain: str
    implemented: bool
    description: str
    status: str
    cycles: int
    last_action_at: Optional[str] = None


class AgentConfigOut(AgentStatusOut):
    """Full agent detail including all static configurable parameters."""

    params: Dict[str, Any] = Field(default_factory=dict)


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


# ----------------------------------------------------------------- market
class CandleOut(BaseModel):
    t: int
    o: float
    h: float
    lo: float
    c: float
    v: float


class TickerOut(BaseModel):
    """Current price + 24h stats, derived from OHLCV (dry-run = synthetic)."""

    last: float
    change_24h_pct: float
    high_24h: float
    low_24h: float
    # Freshness anchor (last candle time, UTC) so the UI can show "atualizado há Xs".
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MacdOut(BaseModel):
    macd: float
    signal: float
    hist: float


class StochOut(BaseModel):
    k: float
    d: float


class BollingerOut(BaseModel):
    up: float
    mid: float
    low: float
    pct_b: float


class IndicatorsOut(BaseModel):
    rsi: Optional[float]
    macd: Optional[MacdOut]
    stoch: Optional[StochOut]
    bb: Optional[BollingerOut]
    atr: Optional[float]
    atr_pct: Optional[float]
    ema9: Optional[float]
    ema21: Optional[float]
    sma20: Optional[float]
    sma50: Optional[float]
    sma200: Optional[float]
    obv_trend: Optional[int]
    volume_ratio: Optional[float]
    current_price: Optional[float]
    # Freshness anchor (last candle time, UTC) so the UI can show "atualizado há Xs".
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RegimeOut(BaseModel):
    regime: str
    confidence: float
    label: str
    active_strategies: List[str]
    # Temporal context (M11): how long the current regime has held + last switch.
    bars_in_regime: Optional[int] = None
    since: Optional[datetime] = None
    last_transition: Optional[str] = None  # e.g. "sideways→strong_uptrend"
    extreme: Optional[str] = None          # euphoria/panic flag (detect_market_extreme)
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SRLevelOut(BaseModel):
    price: float
    strength: int


class LevelsOut(BaseModel):
    support: List[SRLevelOut]
    resistance: List[SRLevelOut]
    fib: List[float]
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VolumeProfileBin(BaseModel):
    price: float
    volume: float
    pct: float


class VolumeProfileOut(BaseModel):
    poc: float
    vah: float
    val: float
    lvn: List[float]
    bins: List[VolumeProfileBin]
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PatternOut(BaseModel):
    name: str
    direction: str
    confidence: float
    target: Optional[float]
    description: str = ""


class ConfidenceFactor(BaseModel):
    """One component of the signal's confidence score (M6).

    Faithfully structures the factors the /signal scorer already computes —
    not the agent's separate 5-factor model.
    """

    name: str
    weight: float        # max points this factor can add to the aggregate
    score: float         # 0..1 normalized contribution toward the chosen action
    contribution: float  # signed points added (+ favors action, − against, 0 neutral)
    note: str = ""       # human-readable rationale (the existing reasons[] text)


class SignalOut(BaseModel):
    action: str
    entry: float
    stop: Optional[float]
    take_profit: Optional[float]
    position_size_pct: float
    rr: Optional[float]
    strategy: str
    confidence: float
    reason: str
    # Transparency (M6): per-factor breakdown + freshness/validity window.
    confidence_factors: List[ConfidenceFactor] = Field(default_factory=list)
    valid_until: Optional[datetime] = None
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TFSnapshot(BaseModel):
    """One timeframe's reading for the multi-timeframe confluence strip (M12)."""

    tf: str
    trend: str                              # "bullish" | "bearish" | "unknown"
    rsi: Optional[float] = None
    macd_hist: Optional[float] = None
    regime: str
    rsi_divergence: Optional[str] = None    # "bullish_divergence" | "bearish_divergence" | None
    macd_divergence: Optional[str] = None


class ConfluenceOut(BaseModel):
    aligned: bool                           # all timeframes agree on direction
    direction: Optional[str] = None         # "bullish" | "bearish" | None (mixed)
    timeframes: List[TFSnapshot]
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ----------------------------------------------------------------- risk
class ProtectionOut(BaseModel):
    scope: str
    value: float
    limit: float
    status: str
    action: str


class CircuitBreakerOut(BaseModel):
    status: str
    triggers: List[str]
    cooldown_hours: int
    cooldown_remaining: Optional[int]


class KellyOut(BaseModel):
    data_quality: str = "ok"  # "ok" | "insufficient"
    trades: int
    win_rate: Optional[float] = None
    avg_win_pct: Optional[float] = None
    avg_loss_pct: Optional[float] = None
    full_kelly: Optional[float] = None
    fraction: Optional[float] = None
    fractional_kelly: Optional[float] = None
    risk_of_ruin: Optional[float] = None


class EquityPoint(BaseModel):
    t: str
    equity: float
    drawdown: float


class RiskConfigOut(BaseModel):
    max_position_size_pct: float
    min_position_size_pct: float
    stop_loss_default_pct: float
    stop_loss_max_pct: float
    take_profit_default_pct: float
    min_risk_reward_ratio: float
    max_daily_loss_pct: float
    max_weekly_loss_pct: float
    max_monthly_loss_pct: float
    circuit_breaker_enabled: bool
    circuit_breaker_trigger_pct: float
    circuit_breaker_consecutive_losses: int
    cooldown_hours: int
    kelly_fraction: float


class RiskConfigPatch(BaseModel):
    max_position_size_pct: Optional[float] = None
    stop_loss_default_pct: Optional[float] = None
    take_profit_default_pct: Optional[float] = None
    max_daily_loss_pct: Optional[float] = None
    max_weekly_loss_pct: Optional[float] = None
    max_monthly_loss_pct: Optional[float] = None
    kelly_fraction: Optional[float] = None
    confirm: bool = Field(default=False, description="Obrigatório confirm=true para gravar alterações de risco")


# ----------------------------------------------------------------- backtest
class BacktestConfigIn(BaseModel):
    strategy: str = "dca"
    # Pair to backtest. Defaults to BTC/USDT (the default is trusted — Pydantic
    # skips validating it — so a custom MARKET_PAIRS without BTC can't break an
    # omitted field). An explicitly supplied pair IS validated against the
    # allowlist below.
    pair: str = Field(default="BTC/USDT")
    initial_capital: float = Field(default=10000.0, gt=0)
    commission_pct: float = Field(default=0.1, ge=0, le=5)
    slippage_bps: int = Field(default=5, ge=0, le=100)
    monte_carlo_sims: int = Field(default=1000, ge=100, le=10000)

    @field_validator("pair")
    @classmethod
    def pair_must_be_allowed(cls, v: str) -> str:
        symbol = v.replace("-", "/").upper() if "/" not in v else v.upper()
        if not is_allowed(symbol):
            raise ValueError(f"Par '{symbol}' não permitido. Configure em MARKET_PAIRS.")
        return symbol


class BacktestResultOut(BaseModel):
    total_trades: int
    win_rate: float
    pnl_pct: float
    pnl_usdt: float
    max_drawdown: float
    sharpe: Optional[float]
    profit_factor: Optional[float]
    avg_win_pct: float
    avg_loss_pct: float
    expectancy: float
    equity: List[EquityPoint]


class MonteCarloOut(BaseModel):
    n: int
    p5: float
    p50: float
    p95: float
    profitable_pct: float
    rejected: bool
    histogram: List[int]
    max_simulated_drawdown: float


class WalkForwardFold(BaseModel):
    window_index: int
    train_sharpe: Optional[float]
    test_sharpe: Optional[float]
    train_pnl_pct: float
    test_pnl_pct: float


class WalkForwardOut(BaseModel):
    valid: bool
    windows: int
    sharpe_deviation: Optional[float]
    folds: List[WalkForwardFold]


class BacktestJobOut(BaseModel):
    job_id: str
    status: str
    result: Optional[BacktestResultOut] = None
    error: Optional[str] = None


# ----------------------------------------------------------------- journal
class JournalEntryCreate(BaseModel):
    setup: str = Field(..., min_length=3)
    emotion_before: int = Field(..., ge=1, le=10)
    emotion_after: Optional[int] = Field(default=None, ge=1, le=10)
    stop_defined: bool
    plan_followed: bool
    pnl_pct: Optional[float] = None
    note: Optional[str] = None


class JournalEntryOut(JournalEntryCreate):
    id: int
    created_at: str


class EmotionBand(BaseModel):
    band: str
    win_rate: float
    trades: int


class JournalMetricsOut(BaseModel):
    by_emotion: List[EmotionBand]
    plan_followed_pnl: Optional[float]
    plan_deviated_pnl: Optional[float]
    discipline_correlation: Optional[float]
    real_win_rate: Optional[float]


# ----------------------------------------------------------------- config
class ConfigOut(BaseModel):
    exchange: str
    dry_run: bool
    initial_capital: float
    orchestrator_interval_seconds: int
    autonomy_level: int
    app_env: str


class ConfigPatch(BaseModel):
    initial_capital: Optional[float] = Field(default=None, gt=0)
    orchestrator_interval_seconds: Optional[int] = Field(default=None, ge=5, le=3600)


class AlertsConfigPatch(BaseModel):
    revenge_size_multiplier: Optional[float] = None
    euphoria_size_multiplier: Optional[float] = None
    overconfidence_margin: Optional[float] = None
    risk_of_ruin_alert_pct: Optional[float] = None


__all__ = [
    "APIResponse", "Meta", "Links", "ErrorResponse",
    "PortfolioMetricsOut", "EquityPoint",
    "AutonomyLevelOut", "HITLConfigOut", "AutonomyLevelPatch",
    "OrderSide", "OrderCreate", "OrderDecisionPatch", "OrderOut",
    "AgentStatusOut", "AgentConfigOut",
    "ProcessEventOut", "AlertOut",
    # market
    "CandleOut", "MacdOut", "StochOut", "BollingerOut", "IndicatorsOut",
    "RegimeOut", "SRLevelOut", "LevelsOut",
    "VolumeProfileBin", "VolumeProfileOut", "PatternOut",
    "ConfidenceFactor", "SignalOut", "TFSnapshot", "ConfluenceOut",
    # risk
    "ProtectionOut", "CircuitBreakerOut", "KellyOut",
    "RiskConfigOut", "RiskConfigPatch",
    # backtest
    "BacktestConfigIn", "BacktestResultOut", "MonteCarloOut",
    "WalkForwardFold", "WalkForwardOut", "BacktestJobOut",
    # journal
    "JournalEntryCreate", "JournalEntryOut", "EmotionBand", "JournalMetricsOut",
    # config
    "ConfigOut", "ConfigPatch", "AlertsConfigPatch",
    # auth (A1)
    "LoginIn", "TwoFactorVerifyIn", "ForgotPasswordIn", "ResetPasswordIn",
    "TwoFactorEnableIn", "TwoFactorDisableIn", "AuthUserOut", "MeOut",
    # rbac (A3)
    "UserOut", "InviteCreate", "InviteOut", "InviteAcceptIn",
    "UserRolePatch", "UserStatusPatch", "RoleOut",
]


# ---------------------------------------------------------------- auth (A1)
class LoginIn(BaseModel):
    email: str
    password: str
    remember: bool = False


class TwoFactorVerifyIn(BaseModel):
    challenge: str
    code: str
    remember: bool = False


class ForgotPasswordIn(BaseModel):
    email: str


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class TwoFactorEnableIn(BaseModel):
    code: str


class TwoFactorDisableIn(BaseModel):
    password: str


class AuthUserOut(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    role: str
    totp_enabled: bool = False


class MeOut(BaseModel):
    """Console boot probe: auth mode + who (if anyone) is logged in."""

    mode: str                       # off | demo | required
    authenticated: bool
    user: Optional[AuthUserOut] = None
    permissions: List[str] = []


# ---------------------------------------------------------------- rbac (A3)
class UserOut(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    role: str
    status: str                     # active | pending | suspended
    totp_enabled: bool = False
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None
    invite_id: Optional[str] = None  # set for pending invites merged into the list


class InviteCreate(BaseModel):
    email: str
    role: str = "visualizador"


class InviteOut(BaseModel):
    id: str
    email: str
    role: str
    expires_at: str


class InviteAcceptIn(BaseModel):
    token: str
    name: str
    password: str = Field(min_length=8)


class UserRolePatch(BaseModel):
    role: str


class UserStatusPatch(BaseModel):
    status: str                     # active | suspended


class RoleOut(BaseModel):
    id: str
    label: str
    permissions: List[str]
