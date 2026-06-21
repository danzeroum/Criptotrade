# Roadmap de Execução v5 — Stack de monitoração (Grafana) em Docker

> Continuação de `roadmap_v4.md`. Capstone visível da observabilidade: um Grafana
> provisionado sobre as métricas Prometheus, tudo em Docker. 2026-06-20.

## Itens entregues
| ID | Item | Status | Evidência |
|----|------|--------|-----------|
| Y1 | Serviço **Grafana** no compose (provisionado, healthcheck, volume) | ✅ | `docker-compose.yml`, perfil padrão |
| Y2 | **Datasource** Prometheus auto-provisionado | ✅ | `monitoring/grafana/provisioning/datasources/datasource.yml` |
| Y3 | **Dashboard** "Criptotrade — Overview" (posições, trades, P&L, win-rate, HTTP rate/p95, portfolio value) | ✅ | `monitoring/grafana/dashboards/criptotrade.json` |
| Y4 | Higiene de imagem: **labels OCI** no Dockerfile | ✅ | `Dockerfile` |
| Y5 | README: como acessar o Grafana | ✅ | `README.md` |

## Como usar
```bash
docker compose up -d          # sobe app, dashboard, orchestrator, prometheus, grafana
# Grafana:    http://localhost:3000  (admin / GF_SECURITY_ADMIN_PASSWORD)
# Prometheus: http://localhost:9090
# API:        http://localhost:8000/metrics
```

## Validação
- `docker compose config -q` (dev) — OK.
- Dashboard/datasource são provisionados na subida; sem testes unitários (config de infra).

## Observação
A pilha de monitoração está completa **em Docker**. Próximos passos substantivos
(PostgreSQL, leader election, multi-réplica, LLM/live) permanecem gated por
infra/decisão do dono ou pelos gatilhos do ADR-005 — ver `docs/pendencia.v2.md`.
