"""Extra coverage for risk/position_sizing.py — edge-case branches."""
from __future__ import annotations

import pytest

from src.risk.position_sizing import (
    KellyCriterion,
    MIN_POSITION_PCT,
    MIN_SAMPLE_FOR_KELLY,
    PositionSizer,
    risk_of_ruin,
)


# ── risk_of_ruin ──────────────────────────────────────────────────────────────

def test_risk_of_ruin_perfect_win_rate_returns_zero():
    """Line 41: win_rate=1.0 → edge=1.0, base=(1-1)/(1+1)=0.0 ≤ 0 → return 0.0."""
    result = risk_of_ruin(win_rate=1.0, bet_fraction=0.1)
    assert result == 0.0


def test_risk_of_ruin_zero_bet_fraction_returns_one():
    """Line 35: bet_fraction=0 → return 1.0 immediately."""
    assert risk_of_ruin(win_rate=0.6, bet_fraction=0.0) == 1.0


def test_risk_of_ruin_zero_win_rate_returns_one():
    """Line 35: win_rate=0 → return 1.0 immediately."""
    assert risk_of_ruin(win_rate=0.0, bet_fraction=0.1) == 1.0


def test_risk_of_ruin_edge_zero_returns_one():
    """Line 38: win_rate=0.5 → edge=0 ≤ 0 → return 1.0."""
    assert risk_of_ruin(win_rate=0.5, bet_fraction=0.1) == 1.0


def test_risk_of_ruin_positive_edge_normal():
    """win_rate=0.6, bet_fraction=0.1 → valid base, valid result."""
    result = risk_of_ruin(win_rate=0.6, bet_fraction=0.1)
    assert 0.0 < result < 1.0


# ── KellyCriterion.full_kelly edge cases ──────────────────────────────────────

def test_full_kelly_avg_loss_zero_returns_none():
    """Line 81: avg_loss_pct=0 → return None."""
    kelly = KellyCriterion(win_rate=0.6, avg_win_pct=2.0, avg_loss_pct=0.0, n_trades=MIN_SAMPLE_FOR_KELLY)
    assert kelly.full_kelly() is None


def test_full_kelly_insufficient_trades_returns_none():
    """Line 79: n_trades < MIN_SAMPLE → return None."""
    kelly = KellyCriterion(win_rate=0.6, avg_win_pct=2.0, avg_loss_pct=1.0, n_trades=5)
    assert kelly.full_kelly() is None


def test_full_kelly_sufficient_trades_computes():
    """n_trades >= MIN_SAMPLE, avg_loss > 0 → returns a float."""
    kelly = KellyCriterion(win_rate=0.6, avg_win_pct=2.0, avg_loss_pct=1.0, n_trades=MIN_SAMPLE_FOR_KELLY)
    result = kelly.full_kelly()
    assert result is not None
    assert isinstance(result, float)


# ── PositionSizer.compute edge cases ─────────────────────────────────────────

def test_compute_entry_equals_stop_returns_min():
    """Line 155: stop_distance_pct=0 (entry==stop) → return MIN_POSITION_PCT."""
    sizer = PositionSizer(capital=10_000.0)
    result = sizer.compute(entry_price=50_000.0, stop_price=50_000.0)
    assert result == MIN_POSITION_PCT


def test_compute_zero_entry_returns_min():
    """Line 151: entry_price=0 → return MIN_POSITION_PCT."""
    sizer = PositionSizer(capital=10_000.0)
    result = sizer.compute(entry_price=0.0, stop_price=48_000.0)
    assert result == MIN_POSITION_PCT


def test_compute_normal_trade():
    """Normal case: result is within [MIN, MAX] range."""
    sizer = PositionSizer(capital=10_000.0, default_risk_pct=1.0)
    result = sizer.compute(entry_price=50_000.0, stop_price=49_000.0)
    assert 0.5 <= result <= 5.0
