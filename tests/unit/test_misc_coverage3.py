"""Third batch of miscellaneous edge-case coverage."""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── SecureToolSandbox._validate_params_safety — forbidden pattern hit ─────────

def test_validate_params_safety_matches_forbidden():
    """Lines 71-72: forbidden pattern matches → returns False."""
    from src.tools.sandbox.secure_executor import SecureToolSandbox

    sandbox = SecureToolSandbox(allow_unsandboxed=True)
    # "leverage.*10x" is a FORBIDDEN_PATTERN
    result = sandbox._validate_params_safety({"action": "leverage 10x position"})
    assert result is False


def test_validate_params_safety_matches_liquidation():
    """Lines 71-72: 'liquidation' pattern → returns False."""
    from src.tools.sandbox.secure_executor import SecureToolSandbox

    sandbox = SecureToolSandbox(allow_unsandboxed=True)
    result = sandbox._validate_params_safety({"risk_level": "liquidation risk"})
    assert result is False


# ── TradeJournal._load — raw not a dict (list) → line 204->exit ──────────────

def test_trade_journal_load_json_list_triggers_exception(tmp_path):
    """Line 204->exit: json.load returns list → .items() raises → except block."""
    from src.journal.trade_journal import TradeJournal

    path = tmp_path / "j.json"
    # Write a JSON list instead of a dict — raw.items() will raise AttributeError
    path.write_text(json.dumps([1, 2, 3]))
    journal = TradeJournal(path)
    # Should not raise — exception is caught and logged
    assert journal.all_entries() == []


# ── RiskAgent._refine_validation — missed_anything=True ──────────────────────

def test_risk_agent_refine_validation_missed_anything():
    """Lines 109-110: missed_anything=True → confidence capped at 0.75."""
    from src.agents.risk_agent import RiskAgent

    agent = RiskAgent()
    validation = {"approved": True, "confidence": 0.9, "issues": [], "warnings": ["w1", "w2", "w3"]}
    reflection = {"missed_anything": True, "too_strict": False, "suggestions": []}
    result = agent._refine_validation(validation, reflection)
    assert result["confidence"] == 0.75
    assert result["requires_review"] is True


# ── MultiTimeframeTrend.classify — EMA None → unknown ────────────────────────

@pytest.mark.asyncio
async def test_mtf_classify_ema_none_returns_unknown():
    """Line 305: ema_fast is None → results[label] = 'unknown'."""
    from src.analysis.indicators import MultiTimeframeTrend, TechnicalIndicators

    classifier = MultiTimeframeTrend()

    # Mock exchange client that returns enough candles
    mock_client = MagicMock()
    mock_client.fetch_ohlcv = AsyncMock(return_value=[
        [i * 1000, 50000.0, 50500.0, 49500.0, 50000.0, 100.0]
        for i in range(52)
    ])

    # Mock TechnicalAnalyzer to return indicators with None EMA
    with patch("src.analysis.indicators.TechnicalAnalyzer") as MockAnalyzer:
        mock_ind = MagicMock(spec=TechnicalIndicators)
        mock_ind.ema_fast = None
        mock_ind.ema_slow = 50_000.0
        MockAnalyzer.return_value.get_latest.return_value = mock_ind

        result = await classifier.classify("BTC/USDT", mock_client)

    # All timeframes should have "unknown" since ema_fast is None
    assert result.primary == "unknown"


# ── Journal API route — entries with no pnl_pct → if pnl_entries: is False ───

def test_journal_metrics_entries_no_pnl(tmp_path, monkeypatch):
    """Lines 144->148: entries exist but pnl_pct=None → pnl_entries empty → real_win_rate=None."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    client = TestClient(create_app())

    # Create an entry with pnl_pct=null
    r = client.post("/v1/journal", json={
        "setup": "test setup",
        "emotion_before": 5,
        "emotion_after": 5,
        "stop_defined": True,
        "plan_followed": True,
        "pnl_pct": None,  # no PnL → won't appear in pnl_entries
        "note": "no pnl",
    })
    assert r.status_code == 201

    response = client.get("/v1/journal/metrics")
    assert response.status_code == 200
    data = response.json()["data"]
    # pnl_entries is empty → real_win_rate stays None
    assert data["real_win_rate"] is None
