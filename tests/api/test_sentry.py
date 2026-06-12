"""Sentry wiring (P3-3): initialization is guarded by SENTRY_DSN."""
from __future__ import annotations

import sentry_sdk

from src.api import main


def test_init_sentry_is_noop_without_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    calls = []
    monkeypatch.setattr(sentry_sdk, "init", lambda *a, **k: calls.append((a, k)))
    main._init_sentry()
    assert calls == []  # no DSN => never initialized


def test_init_sentry_initializes_with_dsn(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://examplePublicKey@o0.ingest.sentry.io/0")
    monkeypatch.setenv("APP_ENV", "production")
    captured: dict = {}
    monkeypatch.setattr(sentry_sdk, "init", lambda **k: captured.update(k))
    main._init_sentry()
    assert captured["dsn"].startswith("https://")
    assert captured["environment"] == "production"
    assert captured["send_default_pii"] is False  # no PII by default


def test_init_sentry_ignores_blank_dsn(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "   ")  # whitespace-only must count as unset
    calls = []
    monkeypatch.setattr(sentry_sdk, "init", lambda *a, **k: calls.append(1))
    main._init_sentry()
    assert calls == []
