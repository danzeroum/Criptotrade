#!/usr/bin/env bash
set -euo pipefail

echo "⚠️  BuildToValue v6 - Rollback"

# Verificar se há backup
if [ ! -f ".BuildToValue/backup/last-deploy.tar.gz" ]; then
    echo "❌ Nenhum backup encontrado"
    exit 1
fi

# Confirmar rollback
read -p "Confirma rollback para versão anterior? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Rollback cancelado"
    exit 0
fi

# Registrar no ledger
echo "{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"rollback_initiated\",\"reason\":\"$1\"}" >> .BuildToValue/ledger/overrides.log

# Parar serviços atuais
echo "🛑 Parando serviços..."
docker-compose down

# Restaurar backup
echo "📦 Restaurando backup..."
tar -xzf .BuildToValue/backup/last-deploy.tar.gz

# Resubir serviços
echo "🚀 Reiniciando serviços..."
docker-compose up -d

# Verificar saúde
sleep 10
if curl -sf http://localhost:8080/actuator/health > /dev/null; then
    echo "✅ Rollback concluído com sucesso"
    echo "{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"rollback_success\"}" >> .BuildToValue/ledger/decisions.log
else
    echo "❌ Falha no rollback - intervenção manual necessária"
    echo "{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"rollback_failed\"}" >> .BuildToValue/ledger/overrides.log
    exit 1
fi
