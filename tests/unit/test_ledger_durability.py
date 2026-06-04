"""LEDGER_DIR honoured so runtime data can live on a mounted volume."""
from __future__ import annotations

from src.core.alerts import Alert, AlertStore
from src.core.ledger import TradingLedger


def test_ledger_uses_ledger_dir_env(tmp_path, monkeypatch):
    # _ledger_dir() reads the env at call time, so no module reload is needed.
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path / "vol" / "ledger"))
    led = TradingLedger()
    led.log_signal(agent="strategy", signal={"action": "BUY"})
    assert led.ledger_path.parent == tmp_path / "vol" / "ledger"
    assert led.ledger_path.exists()


def test_alert_store_uses_ledger_dir_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path / "vol" / "ledger"))
    store = AlertStore()
    store.append(Alert(severity="low", type="t", message="m"))
    assert store.path.parent == tmp_path / "vol" / "ledger"
    assert store.path.exists()


def test_explicit_path_overrides_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DIR", str(tmp_path / "ignored"))
    explicit = tmp_path / "explicit" / "trades.jsonl"
    led = TradingLedger(explicit)
    assert led.ledger_path == explicit
