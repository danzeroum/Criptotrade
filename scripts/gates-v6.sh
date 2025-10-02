#!/usr/bin/env bash
set -euo pipefail

echo "=================="
echo "BuildToValue v6 - Quality Gates Unificados"
echo "=================="

PASS=0
FAIL=0
WARN=0

# Funções auxiliares
pass() { echo "✅ $1"; ((PASS++)); }
fail() { echo "❌ $1"; ((FAIL++)); }
warn() { echo "⚠️  $1"; ((WARN++)); }

# Gate: Configuração Geral
if [ -f ".env.production" ] && [ -f "discovery-consensus.v6.json" ]; then
    pass "Configuração geral OK"
else
    fail "Configuração geral falhou"
fi

# Gate: Padrões Específicos
# Prompt Chaining
if ./scripts/test-prompt-chaining.sh; then
    pass "Prompt Chaining validado"
else
    fail "Prompt Chaining falhou"
fi

# Routing
if ./scripts/test-routing.sh; then
    pass "Routing validado"
else
    fail "Routing falhou"
fi

# Parallelization
if ./scripts/test-parallelization.sh; then
    pass "Parallelization validado"
else
    fail "Parallelization falhou"
fi

# Memory Management
if ./scripts/test-memory-management.sh; then
    pass "Memory Management validado"
else
    fail "Memory Management falhou"
fi

# Multi-Agent Collaboration
if ./scripts/test-multi-agent-collaboration.sh; then
    pass "Multi-Agent Collaboration validado"
else
    fail "Multi-Agent Collaboration falhou"
fi

# Tool Use
if ./scripts/test-tool-use.sh; then
    pass "Tool Use validado"
else
    fail "Tool Use falhou"
fi

# Reasoning Techniques
if ./scripts/test-reasoning-techniques.sh; then
    pass "Reasoning Techniques validado"
else
    fail "Reasoning Techniques falhou"
fi

# Guardrails
if ./scripts/test-guardrails.sh; then
    pass "Guardrails validado"
else
    fail "Guardrails falhou"
fi

# Resultado Final
echo ""
echo "=================="
echo "RESULTADO FINAL"
echo "=================="
echo "✅ Passed: $PASS"
echo "⚠️  Warnings: $WARN"
echo "❌ Failed: $FAIL"

if [ $FAIL -gt 0 ]; then
    echo "❌ QUALITY GATES FAILED"
    exit 1
else
    echo "✅ QUALITY GATES PASSED"
    exit 0
fi
