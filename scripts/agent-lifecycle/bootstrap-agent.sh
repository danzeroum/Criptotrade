#!/usr/bin/env bash
set -euo pipefail

# Bootstrap a minimally viable agent with foundational guardrails and observability.
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")"/../.. && pwd)
CONFIG_DIR="$PROJECT_ROOT/.BuildToValue"

echo "[bootstrap] Initializing agent state..."
mkdir -p "$CONFIG_DIR/runtime"
cp -n "$CONFIG_DIR/prompts/registry.json" "$CONFIG_DIR/runtime/" 2>/dev/null || true

echo "[bootstrap] Agent bootstrapped with minimal capabilities."
