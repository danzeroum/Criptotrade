"""Seventh batch of miscellaneous edge-case coverage."""
from __future__ import annotations

import pytest


# ── ResilientPromptChain — multi-step execution (23->22 outer loop iteration) ─

@pytest.mark.asyncio
async def test_resilient_chain_multi_step_executes_all():
    """Lines 23->22: inner loop completes, outer loop iterates to next step."""
    from src.chains.resilient_chain import ResilientPromptChain, ChainStep

    step1 = ChainStep(name="step1", execute=lambda x: x + 10)
    step2 = ChainStep(name="step2", execute=lambda x: x * 2)
    chain = ResilientPromptChain(steps=[step1, step2])
    result = await chain.execute_with_checkpoints(5)
    assert result == 30  # (5+10)*2


@pytest.mark.asyncio
async def test_resilient_chain_empty_steps_returns_input():
    """Empty steps → loop never executes → returns initial_input unchanged."""
    from src.chains.resilient_chain import ResilientPromptChain

    chain = ResilientPromptChain(steps=[])
    result = await chain.execute_with_checkpoints(42)
    assert result == 42


# ── RiskAgent._validate_signal — entry <= 0 → stop loss block skipped ─────────

@pytest.mark.asyncio
async def test_risk_agent_validate_zero_entry_skips_stop_check():
    """Line 75->80: entry_price=0 → if entry > 0 is False → stop loss block skipped."""
    from src.agents.risk_agent import RiskAgent

    agent = RiskAgent()
    signal = {
        "entry_price": 0.0,   # → False → skip stop loss check
        "stop_loss": 40_000.0,
        "position_size_pct": 1.0,
        "take_profit": 55_000.0,
    }
    result = await agent._validate_signal(signal, {})
    assert isinstance(result, dict)
    assert "warnings" in result
    # No stop loss warning (block was skipped)
    assert not any("Stop loss" in w for w in result["warnings"])


# ── TradeJournal._load — JSON is a list (204->exit) ──────────────────────────

def test_trade_journal_load_json_list_triggers_exception_v2(tmp_path):
    """Line 204->exit confirmed: raw.items() on list → AttributeError → except."""
    import json
    from src.journal.trade_journal import TradeJournal

    path = tmp_path / "j2.json"
    path.write_text(json.dumps(["not", "a", "dict"]))
    journal = TradeJournal(path)
    assert len(journal.all_entries()) == 0



# ── VolumeProfile — edge bin break condition ──────────────────────────────────

def test_volume_profile_edge_bin_break(tmp_path):
    """Line 91: can_go_lower and can_go_higher both False → break."""
    from src.analysis.volume_profile import VolumeProfile

    # Use OHLCV with extreme narrow price range (all prices equal)
    ts = 1_700_000_000_000
    ohlcv = [
        [ts + i * 3600_000, 50_000.0, 50_000.0, 50_000.0, 50_000.0, 100.0]
        for i in range(20)
    ]
    vp = VolumeProfile(ohlcv)
    result = vp.analyze()
    assert result is not None
