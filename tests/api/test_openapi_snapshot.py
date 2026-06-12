"""OpenAPI contract-drift detection (P3-4).

Fails when the live FastAPI schema diverges from the committed snapshot that the
console's TypeScript types are generated from. When the change is intentional,
regenerate both artifacts and commit them:

    python scripts/dump_openapi.py
    npm --prefix docs/design/pages run gen:types
"""
from __future__ import annotations

from scripts.dump_openapi import SNAPSHOT, render


def test_openapi_snapshot_matches_live_schema():
    committed = SNAPSHOT.read_text(encoding="utf-8")
    live = render()
    assert live == committed, (
        "OpenAPI schema drifted from docs/design/pages/openapi.json. Run "
        "`python scripts/dump_openapi.py` and "
        "`npm --prefix docs/design/pages run gen:types`, then commit both."
    )
