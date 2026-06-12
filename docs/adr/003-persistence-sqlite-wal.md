# ADR-003: Estratégia de Persistência do Criptotrade (JSONL → SQLite WAL)

## Status

Aceito — 2026-06-04. **Atualizado 2026-06-12:** o event log do ledger
(`src/core/ledger.py`) foi migrado de JSONL para **SQLite/WAL** (tabela
`ledger_events`, com `event_type` indexado — `get_events` deixa de varrer o log
inteiro), fechando o gatilho de migração descrito abaixo. O contrato de leitura
(`read_all`/`get_events`/`get_process_events`/`get_recent_trades`) foi preservado.
Dados legados em `trades.jsonl` são importados uma vez com
`scripts/migrate_ledger.py`. `alerts.py` permanece em JSONL (baixo volume).

## Contexto

O sistema persiste eventos de trading, ordens, alertas e o event log de processo
(XES) gerados pelos agentes AI. A escolha de mecanismo afeta: durabilidade em
restart, capacidade de query, complexidade operacional e custo de migração futura.

Hoje a persistência é feita em arquivos JSONL append-only sob `LEDGER_DIR`
(`src/core/ledger.py`, `src/core/alerts.py`), montado como volume Docker
(`docker-compose.yml`: `LEDGER_DIR=/app/data/ledger` sobre `./data`). Cada leitura
(`read_all`/`get_events`) varre o arquivo inteiro.

## Decisão

### Atual: JSONL via Volume Docker

Arquivos append-only em `LEDGER_DIR` montado como volume. Adequado para a fase de
validação com 1 operador e baixo volume de eventos. Escrita é O(1) (append);
leitura é O(n) (varredura) — aceitável enquanto o volume diário for baixo.

## Incidente Registrado (obrigatório)

Antes da Fase 4a (commit `2deffd4`, 2026-06-04), o `GuardrailSystem` existia e era
instanciado pelo `RiskAgent`, mas `validate_order` **nunca era chamado no caminho
vivo** — nem no `RiskAgent` nem no `OrderStore`. Em consequência, sinais com
risk-reward < 2.5 (ex.: entry 100 / stop 97 / take_profit 105 → RR 1.67) eram
**aprovados silenciosamente**.

O sistema operou **sem guardrail de risco real desde o início do projeto até
2026-06-04**, quando a Fase 4a ligou `validate_order` nos dois caminhos (live
`RiskAgent` e `OrderStore`, com rejeição automática + evento XES `order_rejected`
+ alerta).

Este registro existe para que decisões futuras de persistência e auditoria
considerem que **a auditoria retroativa de conformidade de risco é impossível
neste período**: o ledger registrou as ordens, mas nenhuma passou por validação de
guardrail, então a ausência de violações registradas não significa conformidade.

## Gatilhos de Migração

| Gatilho | Migrar para | Motivo |
|---------|-------------|--------|
| > 10k eventos/dia | SQLite | Queries com filtro, sem varredura total, sem overhead de rede |
| > 100k eventos/dia | PostgreSQL | Índices, concurrent writes, particionamento |
| > 1 container escrevendo | PostgreSQL | JSONL append não é multi-process safe |
| Auditoria regulatória | PostgreSQL | ACID, backup point-in-time, retenção |

Estimativa de referência: o loop contínuo da Fase 4b a 60s gera ~1.440 ciclos/dia;
com ~12 agentes emitindo `agent_cycle_*`, isso se aproxima de ~17k eventos/dia —
**já acima do gatilho de SQLite**. Por isso este ADR é escrito **antes** de ligar o
loop: a decisão de migração deve ser de planejamento, não de pressão de produção.

## Trade-offs

- **JSONL**: zero dependência, append seguro, legível por humano; **não queryável
  sem varredura total**; não multi-process safe para escrita concorrente.
- **SQLite**: queryável com índices, single-file, sem servidor; **não multi-process**
  para escrita concorrente sob carga.
- **PostgreSQL**: production-grade (ACID, índices, concorrência, backup); **alta
  complexidade operacional** (servidor, migrations, tuning).

## Consequências

- O `AgentRegistry` **não deve** calcular `cycles_today` varrendo o JSONL a cada
  request (degradação O(n); com refresh do dashboard a cada 5s e ~17k eventos/dia,
  seriam milhões de leituras de linha/dia). A Fase 4b adota **agregação em memória**
  (contador por `agent_id` incrementado em `agent_cycle_completed`, reset diário em
  UTC, servido em O(1)). Isto é correção de performance, não otimização opcional.
- O loop contínuo (4b) só inicia com `EXCHANGE_DRY_RUN` configurado
  explicitamente, evitando chamadas de rede reais não intencionais que poluiriam o
  event log e poderiam disparar rate limiting da exchange.
- Quando um gatilho de migração for atingido, a interface de leitura/escrita do
  ledger (`log_*` / `get_events` / `read_all`) deve ser preservada como contrato,
  trocando apenas a implementação por trás — minimizando o blast radius da migração.
