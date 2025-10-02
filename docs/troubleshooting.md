# 🔧 BuildToValue v6 - Troubleshooting

## Problemas Comuns

### 1. Gates falhando sem motivo aparente
**Sintoma**: `./scripts/gates-v6.sh` retorna erro mas testes passam localmente

**Solução**:
```bash
rm -rf .BuildToValue/cache/*
docker-compose down -v
docker-compose up -d
VERBOSE=true ./scripts/gates-v6.sh
```
Registrar override se necessário:
```bash
echo '{"timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","type":"gate_override","gate":"[nome]","reason":"[motivo]"}' >> .BuildToValue/ledger/overrides.log
```

### 2. Performance abaixo da meta
**Sintoma**: P95 > 800ms

**Diagnóstico**:
```bash
./mvnw spring-boot:run -Dspring-boot.run.jvmArguments="-Xmx1024m -XX:+FlightRecorder"
grep "SQL" logs/application.log | tail -100
```
**Soluções comuns**: adicionar índices, implementar cache (Redis), otimizar queries N+1, ajustar pool de conexões.

### 3. Conflito de consenso entre IAs
**Sintoma**: IAs não chegam a consenso após 3 rodadas

**Solução**: ativar fallback humano, registrar decisão manual:
```bash
echo '{"timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","event":"human_fallback","decision":"[escolha]","reason":"[justificativa]"}' >> .BuildToValue/ledger/decisions.log
```

### 4. Mock data não marcado
**Sintoma**: Dados de teste aparecem em produção

**Soluções**:
```java
if (mockEnabled) {
    response.addHeader("X-BTF-Mock", "true");
}
```
```javascript
if (response.headers.get('X-BTF-Mock')) {
    showMockIndicator();
}
```

## Comandos de Diagnóstico
```bash
./scripts/health-check-v6.sh
jq '.level == "ERROR"' < logs/application.json | tail -20
curl -s http://localhost:8080/actuator/prometheus | grep -E "p95|error_rate"
grep "traceId=ABC123" logs/*.log
jq '.event' < .BuildToValue/ledger/decisions.log | sort | uniq -c
```

## Contatos de Emergência
- On-call Engineer: oncall@BuildToValue.com
- Squad Lead: squad@BuildToValue.com
- SRE Team: sre@BuildToValue.com
- Status Page: https://status.BuildToValue.com

## 📚 Glossário
| Termo | Definição |
|-------|-----------|
| ADR | Architecture Decision Record |
| Crisp Pragmatist | Filosofia com disciplina mínima e valor máximo |
| Fast Consensus | Método de decisão por maioria simples entre IAs |
| Foundation Level | Nível de complexidade do projeto |
| Gates | Critérios de qualidade obrigatórios |
| Ledger | Registro imutável de decisões e overrides |
| Mock Data | Dados sintéticos marcados com X-BTF-Mock |
| Must Have | Funcionalidades essenciais |
| P95 | Percentil 95 de latência |
| RFC 7807 | Padrão Problem Details |
| Squad | Conjunto de IAs especializadas |
| TraceId | Identificador de rastreamento |
| Vendor Readiness | Preparação para venda/entrega |

## 🏁 Conclusão
BuildToValue v6 entrega valor real rápido, com rastreabilidade total e foco em vendabilidade.
