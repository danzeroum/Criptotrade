"""Extra coverage for trade_journal.py — _load/_save error paths, all_entries, edge cases."""
from __future__ import annotations

import json
import pytest

from src.journal.trade_journal import TradeEntry, TradeJournal


# ── close_trade: unknown order_id returns None ────────────────────────────────

def test_close_trade_unknown_order_id_returns_none(tmp_path):
    """Lines 135-136: close_trade with unknown id logs warning and returns None."""
    journal = TradeJournal(str(tmp_path / "j.json"))
    result = journal.close_trade("nonexistent_order", exit_price=50_000.0)
    assert result is None


# ── all_entries method ────────────────────────────────────────────────────────

def test_all_entries_returns_all(tmp_path):
    """Line 151: all_entries returns open and closed trades."""
    journal = TradeJournal(str(tmp_path / "j.json"))
    e1 = TradeEntry(order_id="open1", symbol="BTC/USDT", action="BUY", entry_price=50_000.0)
    e2 = TradeEntry(order_id="open2", symbol="ETH/USDT", action="BUY", entry_price=3_000.0)
    journal.record_entry(e1)
    journal.record_entry(e2)
    journal.close_trade("open1", exit_price=51_000.0)
    all_ = journal.all_entries()
    assert len(all_) == 2


# ── TradeEntry.close with entry_price = 0 ────────────────────────────────────

def test_trade_entry_close_with_zero_entry_price():
    """Lines 70->76: when entry_price == 0 the pnl calculation is skipped."""
    entry = TradeEntry(order_id="z", symbol="BTC/USDT", action="BUY", entry_price=0.0)
    entry.close(exit_price=50_000.0)
    # pnl_pct and pnl_usdt must remain None (not calculated)
    assert entry.pnl_pct is None
    assert entry.pnl_usdt is None


# ── _load: exception path ─────────────────────────────────────────────────────

def test_load_corrupted_json_logs_warning_and_continues(tmp_path):
    """Lines 201-207: corrupt JSON in save file — warning is logged, journal works."""
    path = tmp_path / "corrupted.json"
    path.write_text("NOT_VALID_JSON{{{{")  # intentionally corrupt

    journal = TradeJournal(str(path))
    # After failed _load, journal should start empty (not crash)
    assert journal.all_entries() == []


def test_load_bad_entry_data_logs_warning(tmp_path):
    """Lines 201-207: valid JSON but entry data doesn't match TradeEntry fields."""
    path = tmp_path / "bad_entry.json"
    path.write_text(json.dumps({"ord1": {"unexpected_key_only": True}}))

    journal = TradeJournal(str(path))
    assert journal.all_entries() == []


# ── _save: exception path ─────────────────────────────────────────────────────

def test_save_exception_is_swallowed(tmp_path, monkeypatch):
    """Lines 214-215: exception during save — warning logged, no crash."""
    journal = TradeJournal(str(tmp_path / "j.json"))
    e = TradeEntry(order_id="s1", symbol="BTC/USDT", action="BUY", entry_price=50_000.0)
    journal.record_entry(e)

    import builtins

    original_open = builtins.open

    def _bad_open(path, *args, **kwargs):
        if "j.json" in str(path) and "w" in str(args):
            raise PermissionError("read-only")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", _bad_open)

    # close_trade calls _save; should not raise
    journal.close_trade("s1", exit_price=51_000.0)
