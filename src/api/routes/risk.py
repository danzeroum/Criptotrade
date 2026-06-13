"""/v1/risk — expõe proteções, circuit breaker, Kelly e config de risco.

Lê risk_params.yaml para limites e calcula métricas a partir do ledger.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml
from fastapi import APIRouter, Body, Depends, HTTPException

from src.api.deps import get_ledger, get_metrics_calculator
from src.api.schemas import (
    APIResponse,
    CircuitBreakerOut,
    KellyOut,
    ProtectionOut,
    RiskConfigOut,
    RiskConfigPatch,
)
from src.core.ledger import TradingLedger
from src.core.metrics import PortfolioMetricsCalculator

router = APIRouter(prefix="/risk", tags=["risk"])

_RISK_PARAMS_PATH = Path(__file__).resolve().parents[4] / "config" / "strategies" / "risk_params.yaml"
_MIN_KELLY_TRADES = 10


def _load_yaml() -> Dict[str, Any]:
    if not _RISK_PARAMS_PATH.exists():
        return {}
    with _RISK_PARAMS_PATH.open() as f:
        return yaml.safe_load(f) or {}


def _save_yaml(data: Dict[str, Any]) -> None:
    with _RISK_PARAMS_PATH.open("w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def _daily_loss_pct(ledger: TradingLedger, initial_capital: float) -> float:
    """Compute today's realised loss as a % of initial capital."""
    today = datetime.now(timezone.utc).date().isoformat()
    entries = ledger.read_all()
    daily_pnl = sum(
        e.get("data", {}).get("pnl", 0.0)
        for e in entries
        if e.get("event_type") == "position_closed"
        and (e.get("timestamp") or "").startswith(today)
    )
    if initial_capital <= 0:
        return 0.0
    return round(daily_pnl / initial_capital * 100, 4)


def _consecutive_losses(ledger: TradingLedger) -> int:
    entries = [
        e for e in ledger.read_all() if e.get("event_type") == "position_closed"
    ]
    count = 0
    for e in reversed(entries):
        if e.get("data", {}).get("pnl", 0) < 0:
            count += 1
        else:
            break
    return count


@router.get(
    "/protections",
    response_model=APIResponse[List[ProtectionOut]],
    summary="Proteções de drawdown (diário / semanal / mensal)",
)
async def get_protections(
    ledger: TradingLedger = Depends(get_ledger),
    calc: PortfolioMetricsCalculator = Depends(get_metrics_calculator),
) -> APIResponse[List[ProtectionOut]]:
    cfg = _load_yaml()
    limits = cfg.get("loss_limits", {})

    max_daily = limits.get("max_daily_loss_pct", 5.0)
    max_weekly = limits.get("max_weekly_loss_pct", 10.0)
    max_monthly = limits.get("max_monthly_loss_pct", 15.0)

    daily_m = calc.compute(period="1d")
    weekly_m = calc.compute(period="7d")
    monthly_m = calc.compute(period="30d")

    def _prot(scope: str, value_pct: float, limit: float) -> ProtectionOut:
        abs_val = abs(value_pct)
        if abs_val >= limit:
            status = "paused"
            action = "stop"
        elif abs_val >= limit * 0.8:
            status = "warn"
            action = "pause"
        else:
            status = "ok"
            action = "continue"
        return ProtectionOut(scope=scope, value=round(value_pct, 4), limit=limit, status=status, action=action)

    daily_loss = abs(daily_m.pnl_period_pct * 100) if daily_m.pnl_period_pct < 0 else 0.0
    weekly_loss = abs(weekly_m.pnl_period_pct * 100) if weekly_m.pnl_period_pct < 0 else 0.0
    monthly_loss = abs(monthly_m.pnl_period_pct * 100) if monthly_m.pnl_period_pct < 0 else 0.0

    return APIResponse(data=[
        _prot("daily", daily_loss, max_daily),
        _prot("weekly", weekly_loss, max_weekly),
        _prot("monthly", monthly_loss, max_monthly),
    ])


@router.get(
    "/circuit-breaker",
    response_model=APIResponse[CircuitBreakerOut],
    summary="Status do circuit breaker",
)
async def get_circuit_breaker(
    ledger: TradingLedger = Depends(get_ledger),
    calc: PortfolioMetricsCalculator = Depends(get_metrics_calculator),
) -> APIResponse[CircuitBreakerOut]:
    cfg = _load_yaml()
    cb_cfg = cfg.get("loss_limits", {}).get("circuit_breaker", {})

    enabled = cb_cfg.get("enabled", True)
    trigger_loss_pct = cb_cfg.get("trigger_daily_loss_pct", 4.0)
    trigger_consec = cb_cfg.get("trigger_consecutive_losses", 3)
    cooldown_hours = cb_cfg.get("cooldown_period_hours", 24)

    initial_capital = calc.initial_capital
    daily_loss = _daily_loss_pct(ledger, initial_capital)
    consec_losses = _consecutive_losses(ledger)

    triggers = []
    if abs(daily_loss) >= trigger_loss_pct:
        triggers.append(f"Perda diária {abs(daily_loss):.2f}% ≥ {trigger_loss_pct}%")
    if consec_losses >= trigger_consec:
        triggers.append(f"{consec_losses} perdas consecutivas ≥ {trigger_consec}")

    if not enabled:
        status = "disabled"
    elif triggers:
        status = "triggered"
    else:
        status = "armed"

    return APIResponse(data=CircuitBreakerOut(
        status=status,
        triggers=triggers,
        cooldown_hours=cooldown_hours,
        cooldown_remaining=cooldown_hours if status == "triggered" else None,
    ))


@router.get(
    "/kelly",
    response_model=APIResponse[KellyOut],
    summary="Critério de Kelly — f*, fracionado e risco de ruína",
)
async def get_kelly(
    ledger: TradingLedger = Depends(get_ledger),
    calc: PortfolioMetricsCalculator = Depends(get_metrics_calculator),
) -> APIResponse[KellyOut]:
    entries = [e for e in ledger.read_all() if e.get("event_type") == "position_closed"]
    trades = len(entries)

    if trades < _MIN_KELLY_TRADES:
        return APIResponse(data=KellyOut(data_quality="insufficient", trades=trades))

    pnls = [e.get("data", {}).get("pnl", 0.0) for e in entries]
    initial_capital = calc.initial_capital or 10000.0

    pnl_pcts = [p / initial_capital * 100 for p in pnls]
    wins = [p for p in pnl_pcts if p > 0]
    losses = [p for p in pnl_pcts if p < 0]

    win_rate = len(wins) / trades
    avg_win = sum(wins) / len(wins) if wins else 1.0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 1.0

    if avg_loss > 0:
        b = avg_win / avg_loss
        full_kelly = win_rate - ((1 - win_rate) / b) if b > 0 else 0.0
        full_kelly = max(0.0, round(full_kelly, 4))
    else:
        full_kelly = 0.0

    fraction = 0.25
    fractional_kelly = round(full_kelly * fraction, 4)

    if win_rate > 0 and win_rate < 1 and avg_win > 0 and avg_loss > 0:
        p = win_rate
        q = 1 - win_rate
        risk_of_ruin = round(((q / p) ** (1.0 / (avg_loss / avg_win))) * 100, 4) \
            if (avg_loss / avg_win) != 0 else 0.0
        risk_of_ruin = max(0.0, min(100.0, risk_of_ruin))
    else:
        risk_of_ruin = 0.0

    return APIResponse(data=KellyOut(
        data_quality="ok",
        trades=trades,
        win_rate=round(win_rate, 4),
        avg_win_pct=round(avg_win, 4),
        avg_loss_pct=round(avg_loss, 4),
        full_kelly=full_kelly,
        fraction=fraction,
        fractional_kelly=fractional_kelly,
        risk_of_ruin=risk_of_ruin,
    ))


@router.get(
    "/config",
    response_model=APIResponse[RiskConfigOut],
    summary="Parâmetros de risco (lê risk_params.yaml)",
)
async def get_risk_config() -> APIResponse[RiskConfigOut]:
    cfg = _load_yaml()
    pos = cfg.get("position_limits", {})
    sl = cfg.get("stop_loss", {})
    tp = cfg.get("take_profit", {})
    ll = cfg.get("loss_limits", {})
    cb = ll.get("circuit_breaker", {})

    return APIResponse(data=RiskConfigOut(
        max_position_size_pct=pos.get("max_position_size_pct", 5.0),
        min_position_size_pct=pos.get("min_position_size_pct", 1.0),
        stop_loss_default_pct=sl.get("default_pct", 3.0),
        stop_loss_max_pct=sl.get("max_allowed_pct", 5.0),
        take_profit_default_pct=tp.get("default_pct", 9.0),
        min_risk_reward_ratio=tp.get("min_risk_reward_ratio", 1.5),
        max_daily_loss_pct=ll.get("max_daily_loss_pct", 5.0),
        max_weekly_loss_pct=ll.get("max_weekly_loss_pct", 10.0),
        max_monthly_loss_pct=ll.get("max_monthly_loss_pct", 15.0),
        circuit_breaker_enabled=cb.get("enabled", True),
        circuit_breaker_trigger_pct=cb.get("trigger_daily_loss_pct", 4.0),
        circuit_breaker_consecutive_losses=cb.get("trigger_consecutive_losses", 3),
        cooldown_hours=cb.get("cooldown_period_hours", 24),
        kelly_fraction=0.25,
    ))


@router.patch(
    "/config",
    response_model=APIResponse[RiskConfigOut],
    summary="Atualiza parâmetros de risco (grava em risk_params.yaml)",
)
async def patch_risk_config(
    patch: RiskConfigPatch = Body(...),
) -> APIResponse[RiskConfigOut]:
    if not patch.confirm:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "confirmation_required",
                "message": "Defina confirm=true para alterar parâmetros de risco.",
                "docs": "/v1/docs",
            },
        )
    cfg = _load_yaml()

    updates = patch.model_dump(exclude_none=True)
    if "max_position_size_pct" in updates:
        cfg.setdefault("position_limits", {})["max_position_size_pct"] = updates["max_position_size_pct"]
    if "stop_loss_default_pct" in updates:
        cfg.setdefault("stop_loss", {})["default_pct"] = updates["stop_loss_default_pct"]
    if "take_profit_default_pct" in updates:
        cfg.setdefault("take_profit", {})["default_pct"] = updates["take_profit_default_pct"]
    if "max_daily_loss_pct" in updates:
        cfg.setdefault("loss_limits", {})["max_daily_loss_pct"] = updates["max_daily_loss_pct"]
    if "max_weekly_loss_pct" in updates:
        cfg.setdefault("loss_limits", {})["max_weekly_loss_pct"] = updates["max_weekly_loss_pct"]
    if "max_monthly_loss_pct" in updates:
        cfg.setdefault("loss_limits", {})["max_monthly_loss_pct"] = updates["max_monthly_loss_pct"]

    try:
        _save_yaml(cfg)
    except (PermissionError, FileNotFoundError, OSError) as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "config_not_writable",
                "message": "Configuração de risco é somente-leitura neste ambiente.",
                "docs": "/v1/docs",
            },
        ) from exc
    return await get_risk_config()
