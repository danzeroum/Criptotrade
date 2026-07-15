# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/);
o projeto segue versionamento pragmático (paper-trading-first, ver ADR-001).

> **Nota sobre histórico:** o histórico detalhado por sprint vive nos
> `docs/roadmap_v1..v6.md` e nas auditorias datadas (`docs/auditoria-*.md`) —
> esses arquivos são **registros históricos** e preservam os números da época
> (ex.: contagens de testes por sprint). A contagem de testes **canônica atual**
> está no README e no TESTING.md.

## [Não lançado]

### Onda 2 — Higiene estrutural (backend + frontend + docs)
- **R5 (Kelly):** fórmula central do Kelly extraída para
  `src/risk/position_sizing.full_kelly_fraction`, agora **fonte única** consumida
  pelo endpoint `GET /v1/risk/kelly` (que antes reimplementava inline) e por
  `KellyCriterion`. `src/risk/` deixa de ser código morto. Contrato da API
  inalterado. *Plugar Kelly no sizing real (`SquadOrchestrator._position_quantity`)
  permanece como cauda do R5 — ver ADR-006.*
- **R2 (colisões de nome):** classes duplicadas renomeadas por propósito —
  `protocols.SquadOrchestrator`→`A2ASquad`, `adaptive_replanner.AdaptivePlanner`→
  `AdaptiveReplanner`, `continuous_evaluator.ContinuousEvaluator`→
  `AgentPerformanceEvaluator`, `intelligent_forgetting.MemoryStore`→
  `RelevanceMemoryStore`.
- **market_data unificado:** o backtest (`engine._build_market_data`) agora computa
  um `TechnicalIndicators` real + regime (guarda de warmup), em vez de placeholders
  — estratégias dirigidas por indicadores (Grid, MeanReversion) exercitam o mesmo
  caminho do live.
- **Frontend (R8, fatia):** utilitário `.kpi-row` (auto-reflow via `auto-fit`)
  aplicado às linhas de KPI das telas; **sidebar responsiva** < 960px (lacuna do
  briefing). Rollout completo de responsividade/a11y permanece aberto.
- **Docs:** ADR-006 (política de sizing Kelly); `mapeamento-dados.md` §8/§9 e
  `arquitetura.md` §12 sincronizados; `CHANGELOG.md`/`CONTRIBUTING.md`/`SECURITY.md`
  adicionados; `plano-melhorias.md` atualizado.

### Onda 1 — Correções seguras (mergeada, PR #68)
- **Backend:** `ab_tests.jsonl` agora é JSON válido (`json.dumps`);
  `mean_reversion` roteável no regime `sideways`; remoção de dados mortos
  (`RiskAgent.max_daily_loss_pct`, `UnifiedOrchestrator.sandbox`/`chain_manager`,
  `AgentMemorySystem.short_term`); log em vez de `except: pass` silencioso.
- **Frontend:** erros de mutação → toast (HITL/journal/settings/backtest);
  confirmação em 2 etapas ao aprovar/rejeitar ordem; fim da colisão
  `STATUS_VARIANT`/`STATUS_LABEL`; limpeza de arquivos/CSS mortos.
- **Docs:** contagem de testes reconciliada (**416 coletados / 408 passam /
  8 pulados** sem `DATABASE_URL`); ADR-004 documentado + índice corrigido;
  `docs/documentação/` → `docs/data/`; `docs/plano-melhorias.md` criado como fonte
  única do backlog.

## Histórico anterior (v1–v6)
Ver `docs/roadmap_v1.md` … `docs/roadmap_v6.md` (correção & verdade → produção
Docker → observabilidade → métricas de domínio → Grafana → backend PostgreSQL
opcional) e `docs/auditoria-criptotrade-2026-06.md` (remediação P0–P3 + Fase 5b).
