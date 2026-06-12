"""Dump the FastAPI OpenAPI schema to a committed snapshot (P3-4).

The snapshot (``docs/design/pages/openapi.json``) is the source of truth for the
console's generated TypeScript types. Run this after changing any API route, then
regenerate the types:

    python scripts/dump_openapi.py
    npm --prefix docs/design/pages run gen:types

CI fails if either artifact drifts from the live schema (see
``tests/api/test_openapi_snapshot.py`` and the console-build job).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))  # allow `import src...` when run as a script

from src.api.main import create_app  # noqa: E402

SNAPSHOT = _ROOT / "docs" / "design" / "pages" / "openapi.json"


def render() -> str:
    """Return the schema as deterministic, diff-friendly JSON (sorted keys)."""
    schema = create_app().openapi()
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def main() -> None:
    SNAPSHOT.write_text(render(), encoding="utf-8")
    print(f"wrote {SNAPSHOT}")


if __name__ == "__main__":
    main()
