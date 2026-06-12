"""Pre-deploy configuration gate (P3-6).

Static safety check over ``docker-compose.prod.yml`` — refuses an insecure
production config *before* it ships. Complements the runtime fail-closed guard in
``create_app()`` (which checks the live env at boot): this catches an unsafe
*committed* config in CI / before ``docker compose up``.

Usage:
    python scripts/validate_deploy_config.py            # exits non-zero on violation
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

COMPOSE = Path(__file__).resolve().parents[1] / "docker-compose.prod.yml"


def _env_map(environment: Any) -> dict[str, str]:
    """Normalize a compose ``environment`` (list ``K=V`` or dict) to a dict."""
    if isinstance(environment, dict):
        return {k: str(v) for k, v in environment.items()}
    out: dict[str, str] = {}
    for item in environment or []:
        if isinstance(item, str) and "=" in item:
            k, v = item.split("=", 1)
            out[k] = v
    return out


def validation_errors(compose: dict[str, Any]) -> list[str]:
    """Return a list of human-readable safety violations (empty == safe)."""
    errors: list[str] = []
    services = compose.get("services", {})

    app = services.get("app")
    if not app:
        return ["compose has no 'app' service"]
    env = _env_map(app.get("environment", []))

    if env.get("APP_ENV") != "production":
        errors.append("app.APP_ENV must be 'production' (enables the fail-closed guard)")
    if "EXCHANGE_DRY_RUN" not in env:
        errors.append("app.EXCHANGE_DRY_RUN must be set explicitly (deliberate live/dry-run choice)")
    cors = env.get("CORS_ORIGINS", "").strip()
    if not cors or cors == "*":
        errors.append("app.CORS_ORIGINS must be an explicit allowlist, never empty or '*'")

    # Only the edge (nginx) may publish host ports; everything else is internal.
    for name, svc in services.items():
        if name != "nginx" and (svc or {}).get("ports"):
            errors.append(f"service '{name}' must not publish host ports (internal-only)")
    if not (services.get("nginx", {}) or {}).get("ports"):
        errors.append("nginx must publish host ports (80/443) — it is the only ingress")

    return errors


def main() -> int:
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    errors = validation_errors(compose)
    if errors:
        print(f"INSECURE production config in {COMPOSE.name}:")
        for e in errors:
            print(f"  ✗ {e}")
        return 1
    print(f"{COMPOSE.name}: production config OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
