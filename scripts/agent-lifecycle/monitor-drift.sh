#!/usr/bin/env bash
set -euo pipefail

# Monitor agent performance drift using recorded telemetry.
TELEMETRY_DIR=${1:-.BuildToValue/ledger/agent-decisions}

if [[ ! -d "$TELEMETRY_DIR" ]]; then
  echo "[monitor] No telemetry directory found at $TELEMETRY_DIR" >&2
  exit 1
fi

echo "[monitor] Scanning for recent degradation signals..."
ls -t "$TELEMETRY_DIR" | head -n 5
