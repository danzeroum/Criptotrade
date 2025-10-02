#!/usr/bin/env bash
set -euo pipefail

echo "🤖 Crypto AI Trading Platform - Setup Script"
echo "=============================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Utility functions
error() {
    echo -e "${RED}❌ ERROR: $1${NC}" >&2
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

info() {
    echo "ℹ️  $1"
}

# Check prerequisites
check_prerequisites() {
    info "Checking prerequisites..."

    if ! command -v python3 &> /dev/null; then
        error "Python 3 is not installed"
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    info "Python version: $PYTHON_VERSION"

    if command -v bc &> /dev/null; then
        if [ "$(echo "$PYTHON_VERSION < 3.11" | bc)" -eq 1 ]; then
            warning "Python 3.11+ recommended. You have $PYTHON_VERSION"
        fi
    else
        warning "bc not found; skipping detailed version comparison"
    fi

    if ! command -v pip3 &> /dev/null; then
        error "pip3 is not installed"
        exit 1
    fi

    if ! command -v git &> /dev/null; then
        warning "git is not installed (optional)"
    fi

    if command -v docker &> /dev/null; then
        success "Docker found"
    else
        warning "Docker not found (optional)"
    fi

    success "Prerequisites check complete"
    echo ""
}

create_venv() {
    info "Creating virtual environment..."

    if [ -d "venv" ]; then
        warning "Virtual environment already exists. Skipping creation."
    else
        python3 -m venv venv
        success "Virtual environment created"
    fi

    echo ""
}

install_dependencies() {
    info "Installing dependencies..."

    source venv/bin/activate
    pip install --upgrade pip

    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        success "Dependencies installed"
    else
        error "requirements.txt not found"
        exit 1
    fi

    echo ""
}

setup_env() {
    info "Setting up environment variables..."

    if [ -f ".env" ]; then
        warning ".env file already exists. Skipping."
    else
        if [ -f ".env.example" ]; then
            cp .env.example .env
            success ".env file created from .env.example"
            warning "⚠️  IMPORTANT: Edit .env and add your API keys!"
        else
            error ".env.example not found"
            exit 1
        fi
    fi

    echo ""
}

create_directories() {
    info "Creating data directories..."

    mkdir -p .buildtovalue/ledger
    mkdir -p .buildtovalue/consensus
    mkdir -p .buildtovalue/prompts
    mkdir -p .buildtovalue/validations
    mkdir -p data/chroma
    mkdir -p logs

    success "Directories created"
    echo ""
}

initialize_ledger() {
    info "Initializing ledger files..."

    touch .buildtovalue/ledger/trades.jsonl
    touch .buildtovalue/ledger/agent-decisions.jsonl
    touch .buildtovalue/ledger/overrides.log

    if ! grep -q "system_initialized" .buildtovalue/ledger/trades.jsonl 2>/dev/null; then
        echo "{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"system_initialized\",\"version\":\"0.1.0-alpha\"}" >> .buildtovalue/ledger/trades.jsonl
    fi

    success "Ledger initialized"
    echo ""
}

run_tests() {
    info "Running tests..."

    source venv/bin/activate

    if command -v pytest &> /dev/null; then
        if pytest tests/ -v --tb=short 2>&1 | tee /tmp/test_output.log; then
            success "All tests passed"
        else
            warning "Some tests failed. Check output above."
        fi
    else
        warning "pytest not found. Skipping tests."
    fi

    echo ""
}

display_next_steps() {
    echo ""
    echo "=============================================="
    echo "🎉 Setup Complete!"
    echo "=============================================="
    echo ""
    echo "Next steps:"
    echo ""
    echo "1. Edit .env file and add your API keys:"
    echo "   nano .env"
    echo ""
    echo "2. Activate virtual environment:"
    echo "   source venv/bin/activate"
    echo ""
    echo "3. Run validation tests:"
    echo "   ./scripts/validate.sh"
    echo ""
    echo "4. Start dashboard (optional):"
    echo "   streamlit run src/dashboard/app.py"
    echo ""
    echo "5. Run your first trade analysis:"
    echo "   python -c 'from src.orchestration.squad_orchestrator import SquadOrchestrator; print("Ready!")'"
    echo ""
    echo "=============================================="
    echo ""
    echo "📚 Documentation:"
    echo "   - README.md"
    echo "   - docs/ADR/"
    echo "   - .buildtovalue/consensus/"
    echo ""
    echo "🔒 Remember: This is PAPER TRADING only!"
    echo ""
}

main() {
    check_prerequisites
    create_venv
    install_dependencies
    setup_env
    create_directories
    initialize_ledger

    read -r -p "Run tests now? (y/n) " response || response="n"
    echo
    if [[ $response =~ ^[Yy]$ ]]; then
        run_tests
    fi

    display_next_steps
}

main "$@"
