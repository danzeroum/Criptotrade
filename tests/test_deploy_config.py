"""Pre-deploy config safety gate (P3-6)."""
from __future__ import annotations

import yaml

from scripts.validate_deploy_config import COMPOSE, validation_errors


def _compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_committed_prod_compose_is_safe():
    assert validation_errors(_compose()) == []


def test_rejects_wildcard_cors():
    c = _compose()
    c["services"]["app"]["environment"] = [
        "APP_ENV=production", "EXCHANGE_DRY_RUN=true", "CORS_ORIGINS=*",
    ]
    assert any("CORS_ORIGINS" in e for e in validation_errors(c))


def test_rejects_non_production_app_env():
    c = _compose()
    c["services"]["app"]["environment"] = [
        "APP_ENV=dev", "EXCHANGE_DRY_RUN=true", "CORS_ORIGINS=https://x",
    ]
    assert any("APP_ENV" in e for e in validation_errors(c))


def test_rejects_missing_dry_run_flag():
    c = _compose()
    c["services"]["app"]["environment"] = ["APP_ENV=production", "CORS_ORIGINS=https://x"]
    assert any("EXCHANGE_DRY_RUN" in e for e in validation_errors(c))


def test_rejects_internal_service_publishing_ports():
    c = _compose()
    c["services"]["app"]["ports"] = ["8000:8000"]
    assert any("app" in e and "host ports" in e for e in validation_errors(c))
