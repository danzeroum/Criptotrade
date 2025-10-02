#!/usr/bin/env bash
set -euo pipefail

echo "🏗️  Configurando projeto BuildToValue v6..."

# Criar estrutura de diretórios
mkdir -p \
    src/agents \
    src/patterns \
    src/utils \
    tests/unit \
    tests/integration \
    scripts \
    docs \
    monitoring \
    .BuildToValue/ledger

# Copiar arquivos de template
cp .env.template .env.development
echo "✅ Criado .env.development"

# Inicializar Git
if [ ! -d .git ]; then
  git init
fi

git add .
git commit -m "Configuração inicial do BuildToValue v6"

# Tornar scripts executáveis
if ls scripts/*.sh >/dev/null 2>&1; then
  chmod +x scripts/*.sh
fi

echo "✅ Configuração do projeto concluída!"
echo "📋 Próximos passos:"
echo "1. Editar .env.development com suas chaves de API"
echo "2. Executar: ./scripts/setup-environment.sh"
echo "3. Testar: ./scripts/gates-v6.sh"
