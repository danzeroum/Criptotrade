#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Implementando BuildToValue v6.1 Completo..."

./scripts/create-v6.1-structure.sh

pip install --quiet --upgrade pip >/dev/null 2>&1 || true
if [ -f requirements.txt ]; then
  pip install --quiet -r requirements.txt || echo "⚠️  Falha ao instalar dependências opcionais"
fi

./scripts/validate-agents-v6.1.sh

echo "✅ BuildToValue v6.1 implementado com sucesso!"
