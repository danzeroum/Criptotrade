#!/usr/bin/env bash
set -euo pipefail

# Validate agent behavior against orchestration specifications.
TEST_SUITE=${1:-tests/emergent}

echo "[validate] Running emergent behavior suite: $TEST_SUITE"
pytest "$TEST_SUITE"
