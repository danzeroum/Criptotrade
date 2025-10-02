#!/usr/bin/env bash
set -euo pipefail

echo "🚀 BuildToValue v6 - Demo Runner"

# Verificar pré-requisitos
command -v docker >/dev/null 2>&1 || { echo "❌ Docker não instalado"; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "❌ curl não instalado"; exit 1; }

# Subir ambiente
echo "📦 Iniciando containers..."
docker-compose up -d

# Aguardar serviços
echo "⏳ Aguardando serviços (30s)..."
sleep 30

# Verificar saúde
echo "🔍 Verificando health..."
if curl -sf http://localhost:8080/actuator/health > /dev/null; then
    echo "✅ Aplicação saudável"
else
    echo "❌ Aplicação não respondeu"
    exit 1
fi

# Criar dados de demo
echo "📊 Criando dados de demonstração..."
curl -X POST http://localhost:8080/api/v1/demo/seed \
    -H "Content-Type: application/json" \
    -H "X-BTF-Mock: true" \
    -d '{"records": 100}'

echo ""
echo "=================="
echo "DEMO READY"
echo "=================="
echo "🌐 Aplicação: http://localhost:8080"
echo "📊 Grafana: http://localhost:3000 (admin/admin)"
echo "📈 Prometheus: http://localhost:9090"
echo ""
echo "Para parar: docker-compose down"
