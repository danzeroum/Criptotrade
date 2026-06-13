"""Extra coverage for src/api/routes/risk.py — private helpers and edge cases."""
from __future__ import annotations

import yaml
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.core.alerts import AlertBus, AlertStore
from src.core.ledger import TradingLedger
from src.core.metrics import PortfolioMetricsCalculator


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path):
    ledger = TradingLedger(tmp_path / "trades.jsonl")
    app = create_app()
    app.dependency_overrides[deps.get_ledger] = lambda: ledger
    app.dependency_overrides[deps.get_metrics_calculator] = lambda: PortfolioMetricsCalculator(
        ledger, 10_000.0
    )
    tc = TestClient(app)
    tc.ledger = ledger  # type: ignore[attr-defined]
    tc.tmp_path = tmp_path  # type: ignore[attr-defined]
    return tc


def _closed(ledger: TradingLedger, pnl: float, order_id: str = "ord") -> None:
    ledger.log_decision(
        "position_closed",
        {"order_id": order_id, "pnl": pnl},
        timestamp=datetime.now(UTC).isoformat(),
    )


# ── _load_yaml / _save_yaml ───────────────────────────────────────────────────

def test_load_yaml_reads_existing_file(tmp_path, monkeypatch):
    """Lines 35-36: _RISK_PARAMS_PATH exists → file is read."""
    import src.api.routes.risk as risk_mod

    yaml_file = tmp_path / "risk_params.yaml"
    yaml_file.write_text("position_limits:\n  max_position_size_pct: 5.0\n")

    monkeypatch.setattr(risk_mod, "_RISK_PARAMS_PATH", yaml_file)

    cfg = risk_mod._load_yaml()
    assert cfg["position_limits"]["max_position_size_pct"] == 5.0


def test_save_yaml_writes_file(tmp_path, monkeypatch):
    """Lines 40-41: _save_yaml writes yaml to disk."""
    import src.api.routes.risk as risk_mod

    yaml_file = tmp_path / "risk_params.yaml"
    monkeypatch.setattr(risk_mod, "_RISK_PARAMS_PATH", yaml_file)

    risk_mod._save_yaml({"key": "value"})
    loaded = yaml.safe_load(yaml_file.read_text())
    assert loaded["key"] == "value"


# ── _consecutive_losses ───────────────────────────────────────────────────────

def test_consecutive_losses_counts_trailing_losses(client):
    """Lines 65-68: negative pnl entries count consecutive losses."""
    import src.api.routes.risk as risk_mod

    _closed(client.ledger, 100.0, "win")
    _closed(client.ledger, -20.0, "loss1")
    _closed(client.ledger, -30.0, "loss2")

    count = risk_mod._consecutive_losses(client.ledger)
    assert count == 2


def test_consecutive_losses_stops_at_win(client):
    import src.api.routes.risk as risk_mod

    _closed(client.ledger, -10.0, "old_loss")
    _closed(client.ledger, 100.0, "win")
    _closed(client.ledger, -5.0, "recent_loss")

    count = risk_mod._consecutive_losses(client.ledger)
    assert count == 1


# ── _daily_loss_pct: zero initial capital ─────────────────────────────────────

def test_daily_loss_pct_zero_capital_returns_zero(client):
    """Line 55: initial_capital <= 0 → returns 0.0."""
    import src.api.routes.risk as risk_mod

    _closed(client.ledger, -100.0, "loss")
    result = risk_mod._daily_loss_pct(client.ledger, 0.0)
    assert result == 0.0


# ── Circuit breaker: disabled, triggered, armed ───────────────────────────────

def test_circuit_breaker_triggered_by_daily_loss(tmp_path, monkeypatch):
    """Lines 139, 145-146: daily loss triggers circuit breaker."""
    import src.api.routes.risk as risk_mod

    # Create a yaml file that sets a low trigger threshold
    yaml_file = tmp_path / "risk_params.yaml"
    yaml_file.write_text(
        "loss_limits:\n"
        "  circuit_breaker:\n"
        "    enabled: true\n"
        "    trigger_daily_loss_pct: 1.0\n"
        "    trigger_consecutive_losses: 10\n"
        "    cooldown_period_hours: 24\n"
    )
    monkeypatch.setattr(risk_mod, "_RISK_PARAMS_PATH", yaml_file)

    ledger = TradingLedger(tmp_path / "trades.jsonl")
    app = create_app()
    app.dependency_overrides[deps.get_ledger] = lambda: ledger
    app.dependency_overrides[deps.get_metrics_calculator] = lambda: PortfolioMetricsCalculator(
        ledger, 10_000.0
    )
    ledger.log_decision(
        "position_closed",
        {"order_id": "loss", "pnl": -200.0},  # 2% loss > 1% trigger
        timestamp=datetime.now(UTC).isoformat(),
    )

    tc = TestClient(app)
    r = tc.get("/v1/risk/circuit-breaker")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["status"] == "triggered"
    assert d["cooldown_remaining"] == 24


def test_circuit_breaker_triggered_by_consecutive_losses(tmp_path, monkeypatch):
    """Lines 141, 145-146: consecutive losses trigger circuit breaker."""
    import src.api.routes.risk as risk_mod

    yaml_file = tmp_path / "risk_params.yaml"
    yaml_file.write_text(
        "loss_limits:\n"
        "  circuit_breaker:\n"
        "    enabled: true\n"
        "    trigger_daily_loss_pct: 100.0\n"
        "    trigger_consecutive_losses: 2\n"
        "    cooldown_period_hours: 6\n"
    )
    monkeypatch.setattr(risk_mod, "_RISK_PARAMS_PATH", yaml_file)

    ledger = TradingLedger(tmp_path / "trades.jsonl")
    app = create_app()
    app.dependency_overrides[deps.get_ledger] = lambda: ledger
    app.dependency_overrides[deps.get_metrics_calculator] = lambda: PortfolioMetricsCalculator(
        ledger, 10_000.0
    )
    for i in range(2):
        ledger.log_decision(
            "position_closed",
            {"order_id": f"l{i}", "pnl": -10.0},
            timestamp=datetime.now(UTC).isoformat(),
        )

    tc = TestClient(app)
    r = tc.get("/v1/risk/circuit-breaker")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["status"] == "triggered"


def test_circuit_breaker_disabled(tmp_path, monkeypatch):
    """Lines 143-144: enabled=false → status='disabled'."""
    import src.api.routes.risk as risk_mod

    yaml_file = tmp_path / "risk_params.yaml"
    yaml_file.write_text(
        "loss_limits:\n"
        "  circuit_breaker:\n"
        "    enabled: false\n"
    )
    monkeypatch.setattr(risk_mod, "_RISK_PARAMS_PATH", yaml_file)

    app = create_app()
    ledger = TradingLedger(tmp_path / "trades2.jsonl")
    app.dependency_overrides[deps.get_ledger] = lambda: ledger
    app.dependency_overrides[deps.get_metrics_calculator] = lambda: PortfolioMetricsCalculator(
        ledger, 10_000.0
    )
    tc = TestClient(app)
    r = tc.get("/v1/risk/circuit-breaker")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "disabled"


# ── Kelly: all wins / all losses edge cases ───────────────────────────────────

def _fill_closed(ledger: TradingLedger, n: int, pnl: float) -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(n):
        ledger.log_decision(
            "position_closed",
            {"order_id": f"k{i}", "pnl": pnl},
            timestamp=base.isoformat(),
        )


def test_kelly_all_wins_risk_of_ruin_zero(client):
    """Line 201: win_rate=1.0 → risk_of_ruin falls into else (0.0)."""
    _fill_closed(client.ledger, 12, 100.0)  # 12 wins, no losses
    r = client.get("/v1/risk/kelly")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["data_quality"] == "ok"
    assert d["risk_of_ruin"] == 0.0


def test_kelly_all_losses_full_kelly_zero(client):
    """Line 189: avg_loss > 0 but no wins → full_kelly = 0 (edge)."""
    _fill_closed(client.ledger, 12, -50.0)  # 12 losses, no wins
    r = client.get("/v1/risk/kelly")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["data_quality"] == "ok"
    assert d["full_kelly"] == 0.0


# ── PATCH config: additional fields ──────────────────────────────────────────

def test_patch_risk_config_all_fields(tmp_path, monkeypatch):
    """Lines 270, 272, 276, 278: patch with stop_loss, take_profit, weekly/monthly loss."""
    import src.api.routes.risk as risk_mod

    yaml_file = tmp_path / "risk_params.yaml"
    yaml_file.write_text("{}\n")
    monkeypatch.setattr(risk_mod, "_RISK_PARAMS_PATH", yaml_file)

    app = create_app()
    tc = TestClient(app)
    payload = {
        "confirm": True,
        "stop_loss_default_pct": 2.5,
        "take_profit_default_pct": 6.0,
        "max_daily_loss_pct": 3.0,
        "max_weekly_loss_pct": 8.0,
        "max_monthly_loss_pct": 15.0,
    }
    r = tc.patch("/v1/risk/config", json=payload)
    assert r.status_code == 200

    # Verify written to YAML
    written = yaml.safe_load(yaml_file.read_text())
    assert written["stop_loss"]["default_pct"] == 2.5
    assert written["take_profit"]["default_pct"] == 6.0
    assert written["loss_limits"]["max_weekly_loss_pct"] == 8.0
    assert written["loss_limits"]["max_monthly_loss_pct"] == 15.0
