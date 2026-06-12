"""Tests for SecurityConfig — validate_order and validate_tool_call."""
from __future__ import annotations

import pytest

from src.safety.security_config import SecurityConfig


# ── validate_order ────────────────────────────────────────────────────────────

def test_valid_order_passes():
    ok, msg = SecurityConfig.validate_order({"position_size_pct": 2.0, "exchange": "binance"})
    assert ok is True
    assert msg == "OK"


def test_order_exceeds_position_size_rejected():
    ok, msg = SecurityConfig.validate_order({"position_size_pct": 10.0})
    assert ok is False
    assert "Position size" in msg


def test_order_forbidden_pattern_in_notes_rejected():
    ok, msg = SecurityConfig.validate_order({
        "position_size_pct": 1.0,
        "notes": "all-in on BTC",
    })
    assert ok is False
    assert "Forbidden pattern" in msg


def test_order_unknown_exchange_rejected():
    ok, msg = SecurityConfig.validate_order({
        "position_size_pct": 1.0,
        "exchange": "shady_exchange",
    })
    assert ok is False
    assert "not in allowed list" in msg


def test_order_allowed_exchanges():
    for exchange in ("binance", "coinbase", "kraken"):
        ok, _ = SecurityConfig.validate_order({"position_size_pct": 1.0, "exchange": exchange})
        assert ok is True, f"Expected {exchange} to be allowed"


def test_order_no_exchange_field_passes():
    ok, msg = SecurityConfig.validate_order({"position_size_pct": 1.0})
    assert ok is True


# ── validate_tool_call ────────────────────────────────────────────────────────

def test_safe_tool_call_passes():
    ok, msg = SecurityConfig.validate_tool_call("get_price", {"symbol": "BTC/USDT"})
    assert ok is True
    assert msg == "OK"


def test_forbidden_tool_name_rejected():
    ok, msg = SecurityConfig.validate_tool_call("rm", {})
    assert ok is False
    assert "blocked by security policy" in msg


def test_forbidden_tool_case_insensitive():
    ok, _ = SecurityConfig.validate_tool_call("DELETE_RESOURCE".lower(), {})
    assert ok is False


def test_tool_call_with_forbidden_pattern_in_params_rejected():
    ok, msg = SecurityConfig.validate_tool_call("execute_query", {"query": "DROP TABLE users"})
    assert ok is False
    assert "forbidden pattern" in msg.lower()


def test_security_config_post_init_sets_forbidden_patterns():
    cfg = SecurityConfig()
    assert cfg.FORBIDDEN_PATTERNS is not None
    assert len(cfg.FORBIDDEN_PATTERNS) > 0


def test_security_config_custom_forbidden_patterns():
    cfg = SecurityConfig(FORBIDDEN_PATTERNS=["custom.*pattern"])
    assert "custom.*pattern" in cfg.FORBIDDEN_PATTERNS
