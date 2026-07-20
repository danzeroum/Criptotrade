# Handoff: Criptotrade Console — Referência de design + Backlog de execução

## Overview
Pacote de handoff do **Criptotrade Console** — a referência de design e o backlog de melhorias/novas telas do bot de trading `danzeroum/Criptotrade`, produzidos nas auditorias. Destina-se a um dev usando Claude Code no repositório real.

O console de produção já está **entregue** e vive em `docs/design/pages/` (React/esbuild, servido como estático via `build.mjs` → `dist/`), consumindo os endpoints reais `/v1/*`. Não há mais protótipo mockado no pacote: a **referência visual é o próprio console de produção**.

O pacote contém:
1. **Os documentos de handoff** (`docs/`) — auditorias e especificações prontas para virar issues.
2. **Esta referência de design** (tokens + mapa tela × endpoint) — abaixo.

## About the Design Files
A referência de aparência e comportamento é o **console de produção em `docs/design/pages/`** — o front real que este handoff especificou, servido como estático (build via `node build.mjs` a partir de `docs/design/pages/`, saída em `docs/design/pages/dist/`) e alimentado pela API `/v1/*`. Os documentos em `docs/*.html` são as **especificações** (abrir no browser); descrevem layout, componentes por tela, estados e critérios de aceite.

## Fidelity
**High-fidelity (hifi).** Cores, tipografia, espaçamento e interações são finais — os tokens abaixo são a fonte. A fonte de verdade dos números é sempre a API real (`/v1/*`); o console usa estados honestos (carregando / vazio / erro / frescor) quando não há dados, nunca números fabricados.

## Estrutura do pacote
```
design_handoff_criptotrade/
├── README.md                        ← este arquivo (referência de design + backlog)
└── docs/                            ← especificações e auditorias (HTML, abrir no browser)
    ├── Handoff Dev - Criptotrade.html              ← handoff original das telas + rotas
    ├── Handoff Dev - Novas Telas.html              ← telas de expansão + integrações
    ├── Handoff Dev - Telas Administrativas.html    ← A1–A10: auth, RBAC, auditoria, chaves…
    ├── Handoff Dev - Fechamento de Posições (Grid).html ← matching FIFO no backend (pronto p/ execução)
    ├── Plano do Dev - Criptotrade.html             ← plano de remediação (revalidar vs master!)
    ├── Melhorias - Dashboard de Mercado.html       ← M1–M13 + S1–S3 com critérios de aceite
    ├── Validação de Layout - Mercado.html          ← QA de layout com medições (C1–C10)
    └── Validação de Fidelidade - Telas vs Código.html ← mapa tela × endpoint × módulo real
```

O console de produção (não incluído neste pacote de docs) fica em `docs/design/pages/` no repositório: `index.html`, `app.jsx`, `shell.jsx`, `components.jsx`, `charts.jsx`, `screen_*.jsx`, `apiClient.js`, `styles.css`, `build.mjs` (esbuild) e `e2e/` (Playwright).

## Screens / Views
Cada tela mapeia para endpoints reais (validado contra `danzeroum/Criptotrade@master`):

| Tela | Arquivo (em docs/design/pages/) | Endpoint real | Módulo no repo |
|---|---|---|---|
| Visão Geral | screen_overview.jsx | GET /v1/metrics | core/metrics.py, core/ledger.py |
| Mesa Multi-Ativo | screen_desk.jsx | GET /v1/desk/summary · /v1/pairs | api/routes/desk.py, core/pairs.py |
| Mercado | screen_market.jsx | GET /v1/market/* | analysis/* , agents/strategy_agent.py |
| Risco & Capital | screen_risk.jsx | GET /v1/risk/* | agents/risk_agent.py, safety/guardrails.py |
| Console HITL | screen_hitl.jsx | GET/PATCH /v1/orders | hitl/orders.py, hitl/config.py |
| Ordens | screen_orders.jsx | GET /v1/orders · /v1/trades/closed | api/routes/{orders,trades}.py |
| Agentes | screen_agents.jsx | GET /v1/agents | agents/registry.py |
| Diário | screen_journal.jsx | GET /v1/journal | api/routes/journal.py |
| Validação | screen_backtest.jsx | GET/POST /v1/backtest | api/routes/backtest.py |
| Observabilidade | screen_observability.jsx | GET /v1/process/events · /metrics | api/routes/process.py |
| Configurações | screen_settings.jsx | GET/PATCH /v1/hitl/config · /v1/config | hitl/config.py, core/config.py |

Layouts, componentes por tela, estados e critérios de aceite estão detalhados em `docs/` (especialmente Melhorias - Dashboard de Mercado e os Handoffs de telas). Não duplico aqui — os docs são a especificação.

## Interactions & Behavior
- **Navegação:** por `location.hash` (deep-link), com roteamento em `app.jsx`. O botão "Ver no HITL" do Mercado pré-filtra o par de destino.
- **Estados de dados (honestos):** todas as telas usam `LoadingState` / `EmptyState` / `ErrorState` / `FreshnessBadge` (`components.jsx`) + `ErrorBoundary` por tela — carregando com skeleton, vazio com CTA, erro com retry, frescor via `as_of`/`calculated_at` do servidor. Sem números fabricados.
- **HITL:** Aprovar/Rejeitar atualizam a fila com toast; rejeição pede motivo; cards de autonomia 0–3.
- **Modo demonstração (`AUTH_MODE=demo`):** somente leitura — ações desabilitadas com tooltip de descoberta e writes barrados (403); a **fonte dos dados é a API real (paper)**.

## State Management
- `CT_PAIR` (par global) — hook `useCurrentPair` em `components.jsx`; header e telas rebindam ao par. A dimensão de par é indexada por símbolo em todas as telas (Fase 9–11), sem singletons órfãos.
- Estado por tela é local (useState). Sem store global além do par.
- Cada tela consome o endpoint real da tabela acima via `apiClient.js` (`CT_API`); não há dados mockados no bundle de produção — mocks vivem apenas como infraestrutura de teste e2e (injetados pelo Playwright).

## Design Tokens (fonte: docs/design/pages/styles.css)
- **Cores:** bg `#F4F6F8` · surface `#FFFFFF` · surface-2 `#F6F8FA` · surface-3 `#EEF1F4` · border `#E4E8EC` · border-2 `#D5DAE0` · ink `#14181C` · ink-2 `#5B636C` · ink-3 `#8A929B` · ink-4 `#AEB5BD` · accent `#14181C` · up/ok `#0E9D6E` (bg `#E7F6EF`) · down/crit `#DC2B2B` (bg `#FCEAEA`) · warn `#C77F08` (bg `#FBF1DD`) · info `#2563EB` (bg `#E7EEFD`) · violet `#7C5CFC`
- **Tipografia:** IBM Plex Sans (UI, 400–700) · IBM Plex Mono (números/código, `font-variant-numeric: tabular-nums`). Base 14px; títulos de página 20px/600/-.02em; label-xs 10.5px uppercase +.06em.
- **Raios:** --r 9px · --r-lg 13px (cards) · pills 999px. **Sombras:** --sh-sm `0 1px 2px rgba(20,24,28,.05)` · --sh-pop (popovers). **Layout:** --sidebar-w 232px · --header-h 60px · gaps de grade 16px · card padding 18px (12px em densidade compacta).

## Assets
Nenhum binário — ícones são SVG inline (`ICON_PATHS` em `components.jsx`, stroke 24×24), gráficos são SVG gerados. Fontes IBM Plex.

## Estado do handoff (jul/2026)
TODAS as frentes ENTREGUES no produto:
- **Fases 1–8** (PRs #74–#86): Grid FIFO, P0 do console (as_of, HITL), layout responsivo C4–C6, camada administrativa A1–A10 completa (A8 descartado — uso pessoal, não SaaS), DeepSeek.
- **Fases 9–11** (PRs #90–#98): Console Multi-Ativo N1–N9 completo — `GET /v1/pairs` + seletor dinâmico, Mesa Multi-Ativo (landing com SYMBOLS>1, `/v1/desk/summary` batch), slots/exposição/`signal_skipped`, dimensão de par em todas as telas, regras de notificação por par, gestão de pares por UI (DB > env, migration 012), pausa por par sem restart, heatmap toggle manual, watchlists localStorage.
- **Faixa de correções (PRs #100–#103):** semântica spot (SELL nunca abre short + slot cap ciente de lado), gate de dado stub (`data_fallback`), `confidence` no payload da ordem, reset operacional do paper state (posições/breaker/ordens; ledger intocado).

**Backlog registrado (não construído):** correlação de exposição · watchlists server-side · staleness do teste de conexão · hot-reload de conexão · dedup de fills · tuning SELL · i18n de strings · digest de notificações · `ALLOW_SHORTS` (futures).

Os docs em `docs/` permanecem como especificação de referência. Para novas frentes: seguir as convenções estabelecidas (plano antes de código, 1 PR por item, CI verde → merge, `AUTH_MODE=off` bit-compatível, princípios de arquitetura para N).

## Files
Especificações: `docs/*.html`. Console de produção (no repositório): `docs/design/pages/`.
