"""Structured logging + request-id log filter (v3)."""
from __future__ import annotations

import logging

from src.core import config
from src.core.request_context import RequestIdLogFilter, request_id_var


def test_build_formatter_text_by_default(monkeypatch):
    monkeypatch.setattr(config.settings, "log_format", "text")
    fmt = config._build_formatter()
    assert isinstance(fmt, logging.Formatter)
    assert "Json" not in type(fmt).__name__


def test_build_formatter_json_when_configured(monkeypatch):
    monkeypatch.setattr(config.settings, "log_format", "json")
    fmt = config._build_formatter()
    assert "Json" in type(fmt).__name__


def test_settings_ignores_unknown_env_keys(tmp_path):
    # A shared .env (POSTGRES_*, GF_*, arbitrary keys) must not crash startup.
    envf = tmp_path / ".env"
    envf.write_text("APP_ENV=development\nPOSTGRES_DB=x\nGF_SECURITY_ADMIN_USER=a\nFOO=bar\n")
    settings = config.Settings(_env_file=str(envf))
    assert settings.app_env == "development"


def test_request_id_filter_sets_attribute():
    record = logging.LogRecord("n", logging.INFO, "p", 1, "msg", None, None)
    token = request_id_var.set("rid-xyz")
    try:
        RequestIdLogFilter().filter(record)
    finally:
        request_id_var.reset(token)
    assert record.request_id == "rid-xyz"
