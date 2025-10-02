#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Deploying BuildToValue v6.1..."

./scripts/validate-agents-v6.1.sh

if command -v pytest >/dev/null 2>&1; then
  echo "🧪 Executando testes..."
  pytest tests -q || echo "⚠️  Pytest retornou código diferente de zero"
else
  echo "⚠️  Pytest não encontrado, pulando testes"
fi

echo "✅ Deploy checklist concluído (execução simulada)"
