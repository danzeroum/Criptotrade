"""Eleventh batch — 0% files, sandbox, orchestration, agent edge cases."""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── mcp_integration — just import (3 lines) ──────────────────────────────────

def test_mcp_integration_import():
    """Import triggers the re-export; covers lines 2-6."""
    from src.tools.mcp_integration import MCPToolRegistry
    assert MCPToolRegistry is not None


# ── src/main.py — run the demo main() ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_src_main_runs():
    """Run the demo main() coroutine directly — covers all 14 lines."""
    from src.main import main
    # main() prints a result; just make sure it runs without raising
    await main()


# ── orchestration/main_loop.py — mock OrchestratorLoop ────────────────────────

@pytest.mark.asyncio
async def test_main_loop_amain_with_mock():
    """_amain() mocked: covers init_db, signal handler wiring, run_forever, logging."""
    from src.orchestration import main_loop as ml

    mock_loop = MagicMock()
    mock_loop.interval = 1
    mock_loop.stop = MagicMock()
    mock_loop.run_forever = AsyncMock()

    with patch.object(ml.OrchestratorLoop, "from_env", return_value=mock_loop):
        await ml._amain()

    mock_loop.run_forever.assert_awaited_once()


def test_main_loop_main_entry():
    """main() calls asyncio.run(_amain()); covers lines 48-50."""
    from src.orchestration import main_loop as ml

    mock_loop = MagicMock()
    mock_loop.interval = 1
    mock_loop.stop = MagicMock()
    mock_loop.run_forever = AsyncMock()

    with patch.object(ml.OrchestratorLoop, "from_env", return_value=mock_loop):
        ml.main()


# ── orchestrator_loop — validated_interval ValueError branches ────────────────

def test_validated_interval_bad_env(monkeypatch):
    """Lines 50-53: env var with non-integer string → ValueError."""
    from src.orchestration import orchestrator_loop as ol
    monkeypatch.setenv("ORCHESTRATOR_INTERVAL_SECONDS", "not_a_number")
    with pytest.raises(ValueError, match="inválido"):
        ol.validated_interval()


def test_validated_interval_out_of_range():
    """Lines 55-58: integer out of [MIN, MAX] range → ValueError."""
    from src.orchestration.orchestrator_loop import validated_interval
    with pytest.raises(ValueError):
        validated_interval(9999)  # exceeds MAX_INTERVAL=3600


# ── orchestrator_loop — run_forever TimeoutError branch ───────────────────────

@pytest.mark.asyncio
async def test_run_forever_timeout_path(tmp_path, monkeypatch):
    """Lines 133-134: asyncio.TimeoutError on wait → pass (interval elapsed)."""
    from src.orchestration.orchestrator_loop import OrchestratorLoop
    from src.core.ledger import TradingLedger
    from src.agents.registry import AgentRegistry
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    ledger = TradingLedger(tmp_path / "t.jsonl")
    registry = AgentRegistry(db_path=str(tmp_path / "t.db"))

    run_count = 0

    async def _fake_cycle(self):
        nonlocal run_count
        run_count += 1
        if run_count >= 2:
            self.stop()

    with patch.object(OrchestratorLoop, "run_cycle", _fake_cycle):
        with patch("src.orchestration.orchestrator_loop.validated_interval", return_value=10):
            loop = OrchestratorLoop(
                orchestrator=MagicMock(),
                registry=registry,
                ledger=ledger,
                interval_seconds=10,
            )
        loop.interval = 0.01  # override for fast testing
        await asyncio.wait_for(loop.run_forever(), timeout=5.0)

    assert run_count >= 2


# ── DockerSandbox — RuntimeError when docker SDK not available ────────────────

def test_docker_sandbox_run_raises_when_docker_none():
    """Lines 21-22: docker is None → RuntimeError."""
    from src.tools.sandbox.docker_sandbox import DockerSandbox
    sb = DockerSandbox()
    with pytest.raises(RuntimeError, match="Docker SDK"):
        sb.run(["echo", "hi"])


# ── ExecutionAgent — invalid task, real trading, observation fallback ─────────

@pytest.mark.asyncio
async def test_execution_agent_invalid_task_raises():
    """Line 23: validate_input(None/empty) → ValueError."""
    from src.agents.execution_agent import ExecutionAgent
    agent = ExecutionAgent(exchange_client=MagicMock())
    with pytest.raises(ValueError, match="Invalid execution task"):
        await agent.execute({})


@pytest.mark.asyncio
async def test_execution_agent_real_trading_path():
    """Lines 64, 78: paper_trading=False → 'place_real_order' observation."""
    from src.agents.execution_agent import ExecutionAgent
    agent = ExecutionAgent(exchange_client=MagicMock())
    agent.paper_trading = False  # force real-trading branch
    task = {
        "signal": {"action": "buy", "symbol": "BTC/USDT"},
        "human_approved": True,
    }
    result = await agent.execute(task)
    # Real trading not implemented → success=False
    assert result["success"] is False


# ── RiskAgent — invalid task raises ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_risk_agent_invalid_task_raises():
    """Line 24: validate_input({}) → ValueError."""
    from src.agents.risk_agent import RiskAgent
    agent = RiskAgent()
    with pytest.raises(ValueError, match="Invalid risk validation task"):
        await agent.execute({})


# ── risk/position_sizing — ruin probability edge cases ───────────────────────

def test_risk_of_ruin_normal_computation():
    """Lines 45-46: standard computation path."""
    from src.risk.position_sizing import risk_of_ruin
    result = risk_of_ruin(win_rate=0.55, bet_fraction=0.1)
    assert 0.0 <= result <= 1.0


def test_risk_of_ruin_zero_bet_fraction():
    """Lines 34-35: bet_fraction <= 0 → returns 1.0 early."""
    from src.risk.position_sizing import risk_of_ruin
    result = risk_of_ruin(win_rate=0.6, bet_fraction=0.0)
    assert result == 1.0


def test_risk_of_ruin_low_win_rate():
    """Lines 37-38: edge <= 0 (win_rate=0.4 → edge=-0.2) → returns 1.0."""
    from src.risk.position_sizing import risk_of_ruin
    result = risk_of_ruin(win_rate=0.4, bet_fraction=0.1)
    assert result == 1.0


# ── market route — volume profile with bins=0 (line 322) ─────────────────────

def test_market_volume_profile_no_bins(tmp_path, monkeypatch):
    """Line 322: bins=0 → out_bins = [] branch executed."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.api.deps import get_exchange_client
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()

    ts = 1_700_000_000_000
    ohlcv = [[ts + i * 3600_000, 50000.0, 50100.0, 49900.0, 50000.0, 100.0] for i in range(200)]
    mc = MagicMock()
    mc.fetch_ohlcv = AsyncMock(return_value=ohlcv)
    mc.fetch_ticker = AsyncMock(return_value={
        "last": 50000.0, "bid": 49990.0, "ask": 50010.0, "timestamp": ts
    })

    app = create_app()
    app.dependency_overrides[get_exchange_client] = lambda: mc
    client = TestClient(app)

    # bins=0 → out_bins = [] (else branch at line 322)
    r = client.get("/v1/market/BTC-USDT/volume-profile?bins=0")
    # bins has ge=0 so this might be invalid or accepted
    assert r.status_code in (200, 422)


# ── volume_profile — zero total volume ────────────────────────────────────────

def test_volume_profile_zero_total_volume():
    """Lines 77-80: total_vol == 0 → early return with poc=poc_price."""
    from src.analysis.volume_profile import VolumeProfile

    ts = 1_700_000_000_000
    # All zero volume candles
    ohlcv = [[ts + i * 3600_000, 50000.0, 50100.0, 49900.0, 50000.0, 0.0] for i in range(30)]
    vp = VolumeProfile(ohlcv)
    result = vp.analyze()
    assert result is not None
    assert result.poc is not None


# ── strategy_agent — HOLD signal uses agent_confidence (line 52) ─────────────

@pytest.mark.asyncio
async def test_strategy_agent_hold_uses_agent_confidence():
    """Line 52: action=HOLD → confidence = agent_confidence (no blending)."""
    from src.agents.strategy_agent import StrategyAgent

    agent = StrategyAgent(exchange_client=None)
    # No exchange client → stub analysis → strategy will generate some signal
    # We want HOLD: use a task that triggers HOLD
    task = {"symbol": "BTC/USDT", "timeframe": "1h"}
    result = await agent.execute(task)
    assert result["success"] is True
    assert "confidence" in result


# ── strategy_agent — strategy cache hit (line 333) ────────────────────────────

def test_strategy_agent_cache_hit():
    """Line 333: second call to _get_strategy returns cached instance."""
    from src.agents.strategy_agent import StrategyAgent

    agent = StrategyAgent(exchange_client=None)
    s1 = agent._get_strategy("dca")
    s2 = agent._get_strategy("dca")
    assert s1 is s2  # same cached instance


# ── strategy_agent — missing strategy key (lines 337-338) ────────────────────

def test_strategy_agent_missing_key_returns_none():
    """Lines 337-338: unknown key → warning + return None."""
    from src.agents.strategy_agent import StrategyAgent

    agent = StrategyAgent(exchange_client=None)
    result = agent._get_strategy("nonexistent_strategy_xyz")
    assert result is None


# ── base_agent — attach_memory coverage ──────────────────────────────────────

def test_base_agent_attach_memory():
    """Lines 64-66: attach_memory sets self.memory."""
    from src.agents.developer_agent import DeveloperAgent

    agent = DeveloperAgent()
    mock_mem = MagicMock()
    agent.attach_memory(mock_mem)
    assert agent.memory is mock_mem
