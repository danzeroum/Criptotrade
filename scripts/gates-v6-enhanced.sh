#!/usr/bin/env bash
set -euo pipefail

PASS=0
FAIL=0
WARN=0

pass() { echo "✅ $1"; ((PASS++)); }
fail() { echo "❌ $1"; ((FAIL++)); }
warn() { echo "⚠️  $1"; ((WARN++)); }

reflect_on_failure() {
    local gate_name=$1
    local error_log=${2:-""}
    python - <<PY
from dataclasses import dataclass
from typing import Dict

@dataclass
class SimpleReflection:
    suggestion: str
    confidence: float

def reflect(gate: str, log: str) -> SimpleReflection:
    base = f"Analisar falha em {gate}."
    if log:
        base += f" Último log conhecido: {log[:80]}"
    return SimpleReflection(suggestion=base, confidence=0.4)

reflection = reflect(${gate_name!r}, ${error_log!r})
print(reflection.suggestion)
PY
}

run_gate() {
    local description=$1
    shift
    if "$@"; then
        pass "$description"
    else
        fail "$description"
        reflect_on_failure "$description"
    fi
}

run_gate "Configuração geral" test -f .env.production -a -f discovery-consensus.v6.json
run_gate "Prompt Chaining" ./scripts/test-prompt-chaining.sh
run_gate "Routing" ./scripts/test-routing.sh
run_gate "Parallelization" ./scripts/test-parallelization.sh
run_gate "Memory Management" ./scripts/test-memory-management.sh
run_gate "Multi-Agent Collaboration" ./scripts/test-multi-agent-collaboration.sh
run_gate "Tool Use" ./scripts/test-tool-use.sh
run_gate "Reasoning Techniques" ./scripts/test-reasoning-techniques.sh
run_gate "Guardrails" ./scripts/test-guardrails.sh

cat <<SUMMARY

==================
RESULTADO FINAL
==================
✅ Passed: $PASS
⚠️  Warnings: $WARN
❌ Failed: $FAIL
SUMMARY

if [ $FAIL -gt 0 ]; then
    echo "❌ QUALITY GATES FAILED"
    exit 1
fi

echo "✅ QUALITY GATES PASSED"
