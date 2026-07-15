# Plano de Melhorias — Criptotrade

> **Fonte única de verdade do backlog de melhorias.** Consolida sinais antes
> espalhados em vários documentos: o dicionário de dados (`docs/data/mapeamento-dados.md`
> §8 dados mortos · §9 anomalias), os achados priorizados de arquitetura
> (`docs/architecture/arquitetura.md` §12 — **R1–R8**), a auditoria de junho
> (`docs/auditoria-criptotrade-2026-06.md`) e as pendências
> (`docs/pendencia.v1.md`, `pendencia.v2.md`, `docs/acaoPendenteDono.md`).
>
> **Formato:** `[x]` concluído · `[ ]` aberto · cada item com `arquivo:linha`,
> severidade e critério de aceite. Este arquivo é um **tracker vivo** — atualize os
> checkboxes por commit, no estilo da auditoria de junho.
>
> Última atualização: **2026-07-15** (Onda 2).
>
> **Progresso:** Onda 1 ✅ (PR #68) · Onda 2 ✅ higiene estrutural — R2 (renomeações),
> R5 parcial (fonte única do Kelly, ADR-006), market_data unificado, R8 fatia
> (responsividade), docs de projeto (CONTRIBUTING/CHANGELOG/SECURITY). Ver `CHANGELOG.md`.

---

## Onda 1 — Correções seguras (ENTREGUE nesta rodada)

Itens de baixo risco e alta confiança, cada um com teste ou verificação de build.
**Não** tocam o invariante central (paper-trading-first, HITL fail-closed, auditoria).

### Backend
- [x] **B-1 · `ab_tests.jsonl` inválido → JSON válido** — `src/evaluation/ab_testing.py:61`.
  Gravava `f"{payload}"` (repr Python, aspas simples) → não parseável por `json.loads`.
  Agora usa `json.dumps`. Teste: `tests/unit/test_ab_testing.py`. *(mapeamento §9.4)*
- [x] **B-2 · `mean_reversion` roteável por regime** — `src/analysis/regime_detector.py:21`.
  A estratégia estava registrada em `STRATEGY_REGISTRY` mas **nenhum regime a emitia**;
  adicionada ao regime `sideways` (range-bound). Teste de consistência
  registry↔roteamento em `tests/unit/test_analysis.py`. *(mapeamento §9.3)*
- [x] **B-3 · Remoção de dados mortos (§8)** — `RiskAgent.max_daily_loss_pct`
  (`risk_agent.py`), `UnifiedOrchestrator.sandbox`/`.chain_manager`
  (`unified_orchestrator.py`), `AgentMemorySystem.short_term` (`agent_memory.py`).
  Nota: a perda-diária cumulativa já é aplicada no `CircuitBreaker` (orquestrador),
  que tem o contexto de P&L que o RiskAgent não tem — por isso removido em vez de
  duplicar. *(mapeamento §8)*
- [x] **B-4 · Log em vez de `except: pass` silencioso** — `agent_memory.py`
  (falha de escrita no vetor agora loga em `debug` com `exc_info`).

### Frontend (`docs/design/pages/`)
- [x] **F-1 · Erros de mutação → toast** — `screen_hitl`, `screen_journal`,
  `screen_settings`, `screen_backtest` só faziam `console.error`. Agora usam o
  `addToast` (já provido pelo `app.jsx`) para feedback de erro **e** sucesso —
  atende o `docs/design/briefing-ui-telas.md §6`.
- [x] **F-2 · Confirmação em ação financeira** — `screen_hitl` aprovar/rejeitar ordem
  agora exige confirmação em duas etapas (mesmo padrão do paper-order do
  `screen_market`).
- [x] **F-3 · Fim da colisão de nome `STATUS_VARIANT`/`STATUS_LABEL`** — eram dois
  mapas **diferentes** com o mesmo nome (ordens vs agentes), hazard citado pelo
  `build.mjs`. Renomeados para `ORDER_STATUS_*` e `AGENT_STATUS_*`.
- [x] **F-4 · Limpeza morta** — 5 arquivos placeholder `tst` (0/1 byte) → `.gitkeep`
  nas pastas scaffold; `@keyframes flashUp/flashDown` mortos removidos; classe
  `.range` aplicada ao `SliderField` (antes um `<input type=range>` sem estilo) +
  `aria-label`.

### Docs
- [x] **D-1 · Contagem de testes reconciliada** — divergia (121/138/273/324/383/406).
  Fixada em **416 coletados (408 passam + 8 pulados sem `DATABASE_URL`)**, verificada
  em 2026-07-14, em `README.md` e `TESTING.md`.
- [x] **D-2 · Lacuna do ADR-004** — criado `docs/adr/004-reserved.md` (número vago
  explícito) e o índice `docs/adr/README.md` agora lista 004 **e** 005 (antes omitia 005).
- [x] **D-3 · Docs históricos rotulados** — cabeçalho "⚠️ Snapshot histórico" em
  `docs/auditoria-conformidade-validacoes.md` (descrevia stack Java já removida),
  `handoff-codex.md` e `validation-checklist.md`.
- [x] **D-4 · Pasta `docs/documentação/` → `docs/data/`** (ASCII, alinhado às demais
  pastas). Este documento consolidado criado.

---

## Backlog estrutural (ABERTO — exige refactor/decisão)

Itens de maior alcance, deixados fora da Onda 1 para manter PRs pequenos e
revisáveis. Numeração **R#** espelha `arquitetura.md §12`.

### Backend
- [ ] **R1 🔴 · Cluster "BuildToValue" não exercitado pelo trading** — `UnifiedOrchestrator`
  + `planning/routing/consensus/chains/parallel` + agentes de engenharia. Isolar em
  `src/experimental/` ou remover; medir cobertura real. Reduz superfície e confusão.
- [x] **R2 🔴 · Colisões de nome de classe** — 🟢 **FEITO (Onda 2)**: duplicatas
  mortas renomeadas por propósito — `protocols.SquadOrchestrator`→`A2ASquad`,
  `adaptive_replanner.AdaptivePlanner`→`AdaptiveReplanner`,
  `continuous_evaluator.ContinuousEvaluator`→`AgentPerformanceEvaluator`,
  `intelligent_forgetting.MemoryStore`→`RelevanceMemoryStore`. **Resta** `Guardrail`×2
  (ver R3/R2b). *(mapeamento §9.5)*
- [x] **R5 🟠 · `src/risk/` era código morto** — 🟡 **PARCIAL (Onda 2, ADR-006)**:
  fórmula central do Kelly extraída para `full_kelly_fraction` (fonte única), consumida
  pelo `GET /v1/risk/kelly` (não reimplementa mais inline) e por `KellyCriterion` —
  `src/risk/` deixa de ser morto, contrato inalterado. **Resta (cauda R5):** plugar no
  `SquadOrchestrator._position_quantity` (muda o trading — exige validação). *(mapeamento §8, §9)*
- [ ] **R3 🟠 · Política de risco/autonomia duplicada** — duas validações de ordem
  (`GuardrailSystem` vs `SecurityConfig`) e dois modelos de autonomia (limiar US$ vs
  trust-score). Eleger fonte única. *(mapeamento §9.6)*
- [x] **market_data 🟠 · Dois formatos** — 🟢 **FEITO (Onda 2)**: `engine._build_market_data`
  computa `TechnicalIndicators` real + `regime` (guarda de warmup), mantendo os campos
  flat do DCA; Grid/MeanReversion não ficam mais inertes no backtest. *(mapeamento §9.1)*
- [ ] **R6 🟡 · `/v1/agents/{id}/config` servido por dois routers** (`agents` GET,
  `config` PATCH). Consolidar num router. *(mapeamento §9.8)*
- [ ] **CandleOut 🟡 · campo `lo` em vez de `l`** — `schemas.py:216` diverge da
  convenção OHLCV. Renomear com alias de compat. *(mapeamento §9.7)*
- [ ] **R7 🟡 · XES/alerts ainda em JSONL** (ADR-003 deferido) — concluir migração
  para SQLite/Postgres quando o volume justificar.
- [x] **Limpeza 🟡 · dependência `ta` não usada** — 🟢 **FEITO (Onda 2)**: removida do
  `requirements.txt` (nenhum `import ta` no código; indicadores usam numpy/pandas
  direto). Docstring de `indicators.py` corrigida.

### Frontend (trilha própria — `docs/design/pages/`)
- [x] **R8 🟠 · Responsividade real** — 🟡 **PARCIAL (Onda 2)**: utilitário `.kpi-row`
  (auto-fit/reflow) aplicado às linhas de KPI das telas + **sidebar responsiva < 960px**
  (a lacuna do briefing). **Resta** os layouts de 2 colunas restantes e a migração ES
  modules/bundler.
- [ ] **FE 🟠 · Camada de normalização de dados** — mata os objetos `mock*` repetidos
  por tela e o coalescing defensivo `a ?? b` (mock↔API). Centraliza no `data.js`/mapper.
- [ ] **FE 🟡 · a11y das charts** — `Donut/BarChart/ScatterChart/Heatmap/MonteCarloChart/
  KellyCurve` sem `role="img"`/`aria-label`/`<title>`; tooltips só no mouse (sem teclado).
- [ ] **FE 🟡 · Confirmação de nível de autonomia** — hoje o `setLevel` dá feedback via
  toast, mas a troca de nível ainda dispara imediata; adicionar confirmação (modal).
- [ ] **FE 🟡 · Testes e2e de interação** — hoje só smoke de navegação; adicionar
  aprovar-ordem, rodar backtest, submeter diário; dar mock a overview/observability.
- [ ] **FE 🟡 · Formatação numérica única** — rotear tudo por `fmtNum/fmtUsd/fmtPrice`
  de `components.jsx` (remover `_fmt` local de `charts.jsx` e `toLocaleString` inline).

### Docs / Infra
- [x] **DOC 🟡 · Arquivos de projeto ausentes** — 🟢 **FEITO (Onda 2)**: `CONTRIBUTING.md`,
  `CHANGELOG.md`, `SECURITY.md` criados na raiz. *(runbook de deploy único ainda aberto —
  hoje entre README e `acaoPendenteDono`.)*
- [ ] **DOC 🟡 · Onboarding específico** — `docs/tutorials/*` são boilerplate genérico
  "BuildToValue", não ensinam a trabalhar no Criptotrade.
- [ ] **DOC 🟡 · Critérios de go-live divergentes** — `discovery-consensus.v6.json`
  (Sharpe >1.2 / DD <15%) vs ADR-001 (Sharpe >1.5 / DD <10%). Eleger uma fonte.
- [ ] **DOC 🟡 · Gate de cobertura divergente** — 66/68/70/72 citados; `pyproject.toml`
  usa **72**. Padronizar o texto para o valor real e citar a fonte.

---

## Ações que dependem do dono (deploy/prod)

Sem alteração — rastreadas em **`docs/acaoPendenteDono.md`** (DNS, portas 80/443,
`API_KEYS`, cert Let's Encrypt, decisão `EXCHANGE_DRY_RUN`, auth do console, Sentry
DSN, secrets de CD) e **`docs/pendencia.v2.md`** (Redis, Postgres gerenciado, leader
election). O item **P0-0** (verificar config real de produção) segue aberto.

---

## Referências
- `docs/data/mapeamento-dados.md` — dicionário de dados (§8 dados mortos, §9 anomalias).
- `docs/architecture/arquitetura.md` §12 — achados R1–R8 + arquitetura-alvo.
- `docs/uml/arquitetura-uml.md` — classes, sequências, máquina de estado de `Order`.
- `docs/auditoria-criptotrade-2026-06.md` — auditoria P0–P3 (concluída) + Fase 5b.
