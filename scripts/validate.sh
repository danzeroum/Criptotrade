#!/usr/bin/env bash
set -euo pipefail

echo "🔍 Crypto AI Trading Platform - Validation Script"
echo "=================================================="
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PASSED=0
FAILED=0
WARNINGS=0

pass() {
    echo -e "${GREEN}✅ PASS:${NC} $1"
    ((PASSED+=1))
}

fail() {
    echo -e "${RED}❌ FAIL:${NC} $1"
    ((FAILED+=1))
}

warn() {
    echo -e "${YELLOW}⚠️  WARN:${NC} $1"
    ((WARNINGS+=1))
}

info() {
    echo -e "${BLUE}ℹ️  INFO:${NC} $1"
}

section() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  $1"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

validate_structure() {
    section "1. Validating Project Structure"

    local directories=(
        ".buildtovalue/consensus"
        ".buildtovalue/ledger"
        "src/agents"
        "src/core"
        "src/safety"
        "src/orchestration"
        "tests/integration"
        "docs/ADR"
        "config/agents"
        "config/strategies"
    )

    for dir in "${directories[@]}"; do
        if [ -d "$dir" ]; then
            pass "Directory exists: $dir"
        else
            fail "Directory missing: $dir"
        fi
    done

    local files=(
        "requirements.txt"
        ".env.example"
        ".gitignore"
        "README.md"
        "docker-compose.yml"
        ".buildtovalue/consensus/discovery-consensus.v6.json"
        ".buildtovalue/consensus/decision-tree-pro.v6.json"
        "config/agents/constitution.yaml"
        "config/strategies/risk_params.yaml"
    )

    for file in "${files[@]}"; do
        if [ -f "$file" ]; then
            pass "File exists: $file"
        else
            fail "File missing: $file"
        fi
    done
}

validate_python() {
    section "2. Validating Python Environment"

    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        pass "Python version: $PYTHON_VERSION"
    else
        fail "Python 3 not found"
        return
    fi

    if [ -d "venv" ]; then
        pass "Virtual environment exists"
    else
        warn "Virtual environment not found. Run ./scripts/setup.sh"
    fi

    if [[ -n "${VIRTUAL_ENV:-}" ]]; then
        pass "Virtual environment activated"
    else
        warn "Virtual environment not activated. Run: source venv/bin/activate"
    fi
}

validate_imports() {
    section "3. Validating Python Imports"

    if [[ -z "${VIRTUAL_ENV:-}" ]]; then
        warn "Skipping import checks (venv not activated)"
        return
    fi

    local imports=(
        "langchain"
        "fastapi"
        "ccxt"
        "pandas"
        "pydantic"
        "yaml"
    )

    for import in "${imports[@]}"; do
        if python3 -c "import $import" 2>/dev/null; then
            pass "Can import: $import"
        else
            fail "Cannot import: $import"
        fi
    done

    local optional_imports=(
        "chromadb"
    )

    for optional in "${optional_imports[@]}"; do
        if python3 -c "import $optional" 2>/dev/null; then
            pass "Optional import available: $optional"
        else
            warn "Optional import missing: $optional"
        fi
    done

    if python3 -c "from src.agents.base_agent import BaseAgent" 2>/dev/null; then
        pass "Can import: src.agents.base_agent"
    else
        fail "Cannot import: src.agents.base_agent"
    fi
}

validate_config() {
    section "4. Validating Configuration"

    if [ -f ".env" ]; then
        pass ".env file exists"
        if grep -q "your_.*_key_here" .env 2>/dev/null; then
            warn ".env contains placeholder values. Update with real API keys."
        fi
    else
        fail ".env file not found. Run: cp .env.example .env"
    fi

    if command -v python3 &> /dev/null; then
        if python3 -c "import yaml, json; yaml.safe_load(open('config/agents/constitution.yaml'))" 2>/dev/null; then
            pass "constitution.yaml is valid YAML"
        else
            fail "constitution.yaml is invalid"
        fi

        if python3 -c "import yaml; yaml.safe_load(open('config/strategies/risk_params.yaml'))" 2>/dev/null; then
            pass "risk_params.yaml is valid YAML"
        else
            fail "risk_params.yaml is invalid"
        fi

        if python3 -c "import json; json.load(open('.buildtovalue/consensus/discovery-consensus.v6.json'))" 2>/dev/null; then
            pass "discovery-consensus.v6.json is valid JSON"
        else
            fail "discovery-consensus.v6.json is invalid"
        fi
    fi
}

validate_agents() {
    section "5. Validating Agents"

    if [[ -z "${VIRTUAL_ENV:-}" ]]; then
        warn "Skipping agent checks (venv not activated)"
        return
    fi

    local agents=(
        "src.agents.strategy_agent:StrategyAgent"
        "src.agents.risk_agent:RiskAgent"
        "src.agents.execution_agent:ExecutionAgent"
    )

    for agent_path in "${agents[@]}"; do
        module=${agent_path%%:*}
        class=${agent_path##*:}
        if python3 -c "from $module import $class" 2>/dev/null; then
            pass "Can import class: $class"
        else
            fail "Cannot import class: $class"
        fi
    done
}

validate_security() {
    section "6. Validating Security"

    if rg -n "api_key" src/ 2>/dev/null | grep -qi "sk-"; then
        fail "Potential hardcoded API keys detected"
    else
        pass "No hardcoded API keys detected"
    fi

    if grep -q "^\.env$" .gitignore 2>/dev/null; then
        pass ".env is in .gitignore"
    else
        fail ".env is NOT in .gitignore"
    fi

    if [[ -n "${VIRTUAL_ENV:-}" ]]; then
        if python3 -c "from src.safety.guardrails import GuardrailSystem; GuardrailSystem()" 2>/dev/null; then
            pass "GuardrailSystem instantiates correctly"
        else
            fail "GuardrailSystem cannot be instantiated"
        fi
    fi
}

run_tests() {
    section "7. Running Tests"

    if [[ -z "${VIRTUAL_ENV:-}" ]]; then
        warn "Skipping tests (venv not activated)"
        return
    fi

    if ! command -v pytest &> /dev/null; then
        warn "pytest not installed"
        return
    fi

    if pytest tests/ -v --tb=short 2>&1 | tee /tmp/pytest_output.log; then
        pass "All pytest suites passed"
    else
        fail "Some tests failed. Check output above."
    fi
}

validate_docs() {
    section "8. Validating Documentation"

    local adrs=(
        "docs/ADR/001-paper-trading-first.md"
        "docs/ADR/002-agent-architecture.md"
    )

    for adr in "${adrs[@]}"; do
        if [ -f "$adr" ]; then
            pass "ADR exists: $adr"
        else
            fail "ADR missing: $adr"
        fi
    done

    if grep -q "Quick Start" README.md 2>/dev/null; then
        pass "README has Quick Start section"
    else
        warn "README missing Quick Start section"
    fi
}

display_summary() {
    section "Validation Summary"
    echo ""
    echo "Results:"
    echo -e "  ${GREEN}✅ Passed:${NC} $PASSED"
    echo -e "  ${YELLOW}⚠️  Warnings:${NC} $WARNINGS"
    echo -e "  ${RED}❌ Failed:${NC} $FAILED"
    echo ""

    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${GREEN}✅ VALIDATION PASSED!${NC}"
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        if [ $WARNINGS -gt 0 ]; then
            echo "Note: There are $WARNINGS warnings to review."
        fi
        return 0
    else
        echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${RED}❌ VALIDATION FAILED!${NC}"
        echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo "Please fix the $FAILED failed check(s) above."
        echo ""
        return 1
    fi
}

main() {
    validate_structure
    validate_python
    validate_imports
    validate_config
    validate_agents
    validate_security
    run_tests
    validate_docs
    display_summary
}

main "$@"
