"""P3-2 — production fail-closed security guard.

The API is lenient in dev (no ``API_KEYS`` = open, ``CORS_ORIGINS`` = ``*``).
With ``APP_ENV=production`` it must instead refuse to start unless auth and CORS
are explicitly configured — the same fail-loud philosophy as
``test_exchange_dry_run::test_missing_env_raises_on_init``.
"""
from __future__ import annotations

import pytest

from src.api.main import create_app


def test_dev_default_boots_without_keys(monkeypatch):
    # No APP_ENV → dev → lenient: the app builds even with no API_KEYS/CORS.
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert create_app() is not None


def test_production_without_api_keys_refuses_to_boot(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.setenv("CORS_ORIGINS", "https://criptotrade.buildtovalue.cloud")
    with pytest.raises(RuntimeError, match="API_KEYS"):
        create_app()


def test_production_wildcard_cors_refuses_to_boot(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("API_KEYS", "strong-key-1")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        create_app()


def test_production_empty_cors_refuses_to_boot(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("API_KEYS", "strong-key-1")
    monkeypatch.setenv("CORS_ORIGINS", "")
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        create_app()


def test_production_with_keys_and_explicit_cors_boots(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("API_KEYS", "strong-key-1,strong-key-2")
    monkeypatch.setenv("CORS_ORIGINS", "https://criptotrade.buildtovalue.cloud")
    assert create_app() is not None


def test_guard_is_case_insensitive_on_app_env(monkeypatch):
    # "Production" / "PRODUCTION" must trip the guard too, not just lowercase.
    monkeypatch.setenv("APP_ENV", "Production")
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.setenv("CORS_ORIGINS", "https://criptotrade.buildtovalue.cloud")
    with pytest.raises(RuntimeError, match="API_KEYS"):
        create_app()
