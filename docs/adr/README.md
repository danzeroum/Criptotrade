# Architecture Decision Records (ADRs)

Decisões de arquitetura do **Criptotrade**, conectadas ao código real. Um único
diretório (`docs/adr/`, minúsculo) com numeração sequencial — consolidado a partir
dos três diretórios ADR antigos (`docs/ADR/`, `docs/ADRs/`, `docs/adr/`), removendo
o boilerplate de metodologia que não descrevia o sistema.

| # | Decisão | Status |
|---|---------|--------|
| [001](001-paper-trading-first.md) | Paper Trading First — validar estratégias sem risco real (base do `EXCHANGE_DRY_RUN`) | Aceita |
| [002](002-agent-architecture.md) | Arquitetura Multi-Agente — Strategy / Risk / Execution sob o Squad Orchestrator | Aceita |
| [003](003-persistence-sqlite-wal.md) | Persistência — JSONL (ledger/XES) + SQLite WAL (estado cross-process) | Aceito |
| [004](004-reserved.md) | *Número reservado — não utilizado* (a sequência salta de 003 para 005) | Vago |
| [005](005-scaling-path.md) | Caminho de Escalabilidade — single-host → horizontal (Redis/Postgres opt-in) | Aceita |

Novos ADRs: copie [`ADR-Template.md`](ADR-Template.md), use o próximo número
sequencial livre (**006** em diante — ver ADR-004) e adicione a linha na tabela acima.
