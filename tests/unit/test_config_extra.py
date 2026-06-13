"""Extra coverage for src/core/config.py — import + function paths."""
from __future__ import annotations

import logging

import pytest

pydantic_settings = pytest.importorskip("pydantic_settings",
                                        reason="pydantic_settings not installed")


def test_import_config_covers_module_level():
    """Importing config runs configure_logging + validate_configuration at module level."""
    import src.core.config as cfg  # noqa: F401 — side-effect import

    assert cfg.settings is not None
    assert cfg.PROJECT_ROOT is not None


def test_get_risk_params_returns_expected_keys():
    from src.core.config import get_risk_params

    params = get_risk_params()
    assert "max_position_size_pct" in params
    assert "stop_loss_pct" in params
    assert "max_daily_loss_pct" in params
    assert "max_concurrent_positions" in params


def test_get_resource_limits_returns_expected_keys():
    from src.core.config import get_resource_limits

    limits = get_resource_limits()
    assert "max_tokens_per_interaction" in limits
    assert "timeout_seconds" in limits
    assert "max_api_cost_per_task" in limits


def test_is_paper_trading_development_mode():
    """app_env=development → always True regardless of testnet flag."""
    from src.core import config as cfg

    orig = cfg.settings.app_env
    cfg.settings.app_env = "development"
    try:
        assert cfg.is_paper_trading() is True
    finally:
        cfg.settings.app_env = orig


def test_is_paper_trading_production_testnet(monkeypatch):
    from src.core import config as cfg

    monkeypatch.setattr(cfg.settings, "app_env", "production")
    monkeypatch.setattr(cfg.settings, "exchange_testnet", True)
    assert cfg.is_paper_trading() is True


def test_is_paper_trading_production_live(monkeypatch):
    from src.core import config as cfg

    monkeypatch.setattr(cfg.settings, "app_env", "production")
    monkeypatch.setattr(cfg.settings, "exchange_testnet", False)
    assert cfg.is_paper_trading() is False


def test_get_autonomy_config_default():
    from src.core.config import get_autonomy_config

    cfg = get_autonomy_config()
    assert "level" in cfg
    assert "description" in cfg
    assert "hitl_required" in cfg


def test_get_autonomy_config_unknown_level(monkeypatch):
    from src.core import config as cfg

    monkeypatch.setattr(cfg.settings, "autonomy_level", 99)
    result = cfg.get_autonomy_config()
    assert result["description"] == "Unknown"


def test_validate_configuration_success(monkeypatch):
    """All checks pass → logs info, no exception."""
    from src.core import config as cfg

    monkeypatch.setattr(cfg.settings, "google_api_key", "test-key")
    monkeypatch.setattr(cfg.settings, "exchange_testnet", True)
    monkeypatch.setattr(cfg.settings, "max_position_size_pct", 5.0)
    monkeypatch.setattr(cfg.settings, "stop_loss_pct", 3.0)
    monkeypatch.setattr(cfg.settings, "autonomy_level", 1)
    monkeypatch.setattr(cfg.settings, "app_env", "development")
    monkeypatch.setattr(cfg.settings, "hitl_approval_required", True)
    cfg.validate_configuration()  # must not raise


def test_validate_configuration_high_position_size_warning(monkeypatch, caplog):
    from src.core import config as cfg

    monkeypatch.setattr(cfg.settings, "google_api_key", "test-key")
    monkeypatch.setattr(cfg.settings, "max_position_size_pct", 15.0)
    monkeypatch.setattr(cfg.settings, "stop_loss_pct", 3.0)
    monkeypatch.setattr(cfg.settings, "exchange_testnet", True)
    monkeypatch.setattr(cfg.settings, "autonomy_level", 1)
    monkeypatch.setattr(cfg.settings, "app_env", "development")
    monkeypatch.setattr(cfg.settings, "hitl_approval_required", True)
    with caplog.at_level(logging.WARNING, logger="src.core.config"):
        cfg.validate_configuration()
    assert any("MAX_POSITION_SIZE_PCT" in r.message for r in caplog.records)


def test_validate_configuration_high_stop_loss_warning(monkeypatch, caplog):
    from src.core import config as cfg

    monkeypatch.setattr(cfg.settings, "google_api_key", "test-key")
    monkeypatch.setattr(cfg.settings, "stop_loss_pct", 8.0)
    monkeypatch.setattr(cfg.settings, "max_position_size_pct", 5.0)
    monkeypatch.setattr(cfg.settings, "exchange_testnet", True)
    monkeypatch.setattr(cfg.settings, "autonomy_level", 1)
    monkeypatch.setattr(cfg.settings, "app_env", "development")
    monkeypatch.setattr(cfg.settings, "hitl_approval_required", True)
    with caplog.at_level(logging.WARNING, logger="src.core.config"):
        cfg.validate_configuration()
    assert any("STOP_LOSS_PCT" in r.message for r in caplog.records)


def test_validate_configuration_live_trading_warning(monkeypatch, caplog):
    from src.core import config as cfg

    monkeypatch.setattr(cfg.settings, "google_api_key", "test-key")
    monkeypatch.setattr(cfg.settings, "exchange_testnet", False)
    monkeypatch.setattr(cfg.settings, "max_position_size_pct", 5.0)
    monkeypatch.setattr(cfg.settings, "stop_loss_pct", 3.0)
    monkeypatch.setattr(cfg.settings, "autonomy_level", 1)
    monkeypatch.setattr(cfg.settings, "app_env", "development")
    monkeypatch.setattr(cfg.settings, "hitl_approval_required", True)
    with caplog.at_level(logging.WARNING, logger="src.core.config"):
        cfg.validate_configuration()
    assert any("LIVE" in r.message for r in caplog.records)


def test_validate_configuration_high_autonomy_production_warning(monkeypatch, caplog):
    from src.core import config as cfg

    monkeypatch.setattr(cfg.settings, "google_api_key", "test-key")
    monkeypatch.setattr(cfg.settings, "exchange_testnet", True)
    monkeypatch.setattr(cfg.settings, "max_position_size_pct", 5.0)
    monkeypatch.setattr(cfg.settings, "stop_loss_pct", 3.0)
    monkeypatch.setattr(cfg.settings, "autonomy_level", 3)
    monkeypatch.setattr(cfg.settings, "app_env", "production")
    monkeypatch.setattr(cfg.settings, "hitl_approval_required", True)
    with caplog.at_level(logging.WARNING, logger="src.core.config"):
        cfg.validate_configuration()
    assert any("AUTONOMY_LEVEL" in r.message for r in caplog.records)


def test_validate_configuration_hitl_inconsistency_raises(monkeypatch):
    from src.core import config as cfg

    monkeypatch.setattr(cfg.settings, "google_api_key", "test-key")
    monkeypatch.setattr(cfg.settings, "exchange_testnet", True)
    monkeypatch.setattr(cfg.settings, "max_position_size_pct", 5.0)
    monkeypatch.setattr(cfg.settings, "stop_loss_pct", 3.0)
    monkeypatch.setattr(cfg.settings, "autonomy_level", 1)
    monkeypatch.setattr(cfg.settings, "app_env", "development")
    monkeypatch.setattr(cfg.settings, "hitl_approval_required", False)
    with pytest.raises(ValueError, match="Invalid configuration"):
        cfg.validate_configuration()


def test_configure_logging_with_empty_handlers(monkeypatch, tmp_path):
    """Lines 99-110: file handler is created only when root logger has no handlers."""
    from src.core import config as cfg
    import logging

    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    root_logger.handlers.clear()

    monkeypatch.setattr(cfg, "LOGS_DIR", tmp_path)
    try:
        cfg.configure_logging()
        assert len(root_logger.handlers) >= 1
    finally:
        # Close any FileHandlers added, then restore
        for h in list(root_logger.handlers):
            h.close()
        root_logger.handlers = original_handlers
