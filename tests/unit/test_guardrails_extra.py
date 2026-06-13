"""Extra coverage for safety/guardrails.py — GuardrailSystem branch paths."""
from __future__ import annotations

from src.safety.guardrails import GuardrailSystem


def _order(**kw):
    base = {
        "action": "BUY",
        "entry_price": 50_000.0,
        "position_size_pct": 3.0,
        "stop_loss": 48_000.0,
        "take_profit": None,
    }
    base.update(kw)
    return base


# ── __post_init__ with explicit rules skips default setup ────────────────────

def test_post_init_with_explicit_rules_skips_default():
    """Line 27->exit: when rules are provided at construction, defaults skipped."""
    custom_rule = lambda order: (True, "")
    gs = GuardrailSystem(rules=[custom_rule])
    assert gs.rules == [custom_rule]
    # The default 4 checks (position_size, stop_loss, etc.) are NOT added
    assert len(gs.rules) == 1


# ── check_stop_loss edge cases ────────────────────────────────────────────────

def test_check_stop_loss_zero_entry_price_passes():
    """Line 70->77: when entry=0, the action-specific checks are skipped."""
    gs = GuardrailSystem()
    order = _order(entry_price=0.0, stop_loss=100.0)
    ok, _ = gs.check_stop_loss(order)
    assert ok is True


def test_check_stop_loss_sell_stop_below_entry_fails():
    """Line 75: SELL order where stop_loss <= entry is rejected."""
    gs = GuardrailSystem()
    order = _order(action="SELL", entry_price=50_000.0, stop_loss=49_000.0)
    ok, reason = gs.check_stop_loss(order)
    assert ok is False
    assert "above entry" in reason


def test_check_stop_loss_buy_stop_above_entry_fails():
    """BUY order where stop_loss >= entry is rejected."""
    gs = GuardrailSystem()
    order = _order(action="BUY", entry_price=50_000.0, stop_loss=51_000.0)
    ok, reason = gs.check_stop_loss(order)
    assert ok is False
    assert "below entry" in reason


# ── check_risk_reward skips when entry/stop/target missing ───────────────────

def test_check_risk_reward_skips_when_no_target():
    """Lines 94->99: take_profit=None → check skipped, returns True."""
    gs = GuardrailSystem()
    order = _order(entry_price=50_000.0, stop_loss=48_000.0, take_profit=None)
    ok, _ = gs.check_risk_reward(order)
    assert ok is True


def test_check_risk_reward_skips_when_entry_zero():
    """entry=0 → the whole RR block is skipped, returns True."""
    gs = GuardrailSystem()
    order = _order(entry_price=0.0, stop_loss=0.0, take_profit=0.0)
    ok, _ = gs.check_risk_reward(order)
    assert ok is True


# ── check_market_conditions ───────────────────────────────────────────────────

def test_check_market_conditions_empty_context_passes():
    """Lines 120->127: no market_context → fast-pass (True)."""
    gs = GuardrailSystem()
    ok, _ = gs.check_market_conditions(_order(market_context=None))
    assert ok is True


def test_check_market_conditions_no_atr_bb_passes():
    """Context present but no atr/bb_middle → volatility check skipped."""
    gs = GuardrailSystem()
    order = _order(market_context={"atr": None, "bb_middle": None, "volume_ratio": 1.0})
    ok, _ = gs.check_market_conditions(order)
    assert ok is True


def test_check_market_conditions_high_volatility_blocks():
    """atr/bb_middle > 0.10 → rejected."""
    gs = GuardrailSystem()
    order = _order(market_context={"atr": 600.0, "bb_middle": 5_000.0, "volume_ratio": 1.0})
    ok, reason = gs.check_market_conditions(order)
    assert ok is False
    assert "Extreme volatility" in reason


def test_check_market_conditions_thin_liquidity_blocks():
    """volume_ratio < 0.3 → rejected."""
    gs = GuardrailSystem()
    order = _order(market_context={"atr": 10.0, "bb_middle": 50_000.0, "volume_ratio": 0.1})
    ok, reason = gs.check_market_conditions(order)
    assert ok is False
    assert "liquidity" in reason
