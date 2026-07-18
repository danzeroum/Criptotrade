# Handoff: Criptotrade Console — Protótipo de demonstração + Backlog de execução

## Overview
Pacote de handoff do **Criptotrade Console** — o front-end de demonstração (dados mockados) do bot de trading `danzeroum/Criptotrade`, mais todo o backlog de melhorias e novas telas produzido nas auditorias. Destina-se a um dev usando Claude Code no repositório real.

O pacote contém duas coisas distintas:
1. **O protótipo demo** (`prototype/`) — console React completo, 10 telas, dados mockados determinísticos, botão "Como funciona de verdade" por tela e tooltips de descoberta em todos os controles. Pensado para demonstração pública; depois, se houver interesse, o projeto real roda na VPS.
2. **Os documentos de handoff** (`docs/`) — auditorias e especificações prontas para virar issues.

## About the Design Files
Os arquivos em `prototype/` são **referências de design em HTML/React (Babel standalone)** — um protótipo navegável que mostra aparência e comportamento pretendidos. **Não são código de produção para copiar diretamente.** A tarefa é recriar/integrar essas telas no ambiente do produto real (o repositório Python serve a API; o front pode ser servido como estático ou portado para o stack que o time escolher), usando os padrões do codebase. O protótipo roda standalone: basta abrir `prototype/Criptotrade Console.html` num servidor estático (os `.jsx` são transpilados no browser via Babel; requer rede para os CDNs de React/Babel/Google Fonts).

## Fidelity
**High-fidelity (hifi).** Cores, tipografia, espaçamento e interações são finais. Recriar pixel-perfect usando os tokens abaixo. Os dados são mockados (`data.js`, `data_ext.js`) e determinísticos de propósito — a fonte de verdade dos números reais são os endpoints `/v1/*` do repo.

## Estrutura do pacote
```
design_handoff_criptotrade/
├── README.md                        ← este arquivo
├── prototype/                       ← protótipo demo completo (abrir Criptotrade Console.html)
│   ├── Criptotrade Console.html     ← entry point (carrega tudo)
│   ├── styles.css                   ← TODOS os design tokens + componentes CSS
│   ├── data.js · data_ext.js        ← mock determinístico (single source dos dados demo)
│   ├── tooltips.js                  ← engine de tooltip por [data-tip] (vanilla, delegação)
│   ├── explain.jsx                  ← botão/modal "Como funciona de verdade" por tela
│   ├── app.jsx                      ← root: roteamento por estado, toast, telas
│   ├── shell.jsx                    ← Sidebar (NAV com tips) + Header (par/regime/CB/autonomia)
│   ├── components.jsx               ← Icon, Card, Btn, Badge, Seg, Tabs, PairSelect, estados
│   ├── charts.jsx                   ← CandleChart, sparklines, gauges (SVG)
│   └── screen_*.jsx                 ← 10 telas (overview, market, risk, hitl, orders,
│                                      agents, journal, backtest, observability, settings)
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

## Screens / Views (10)
Cada tela mapeia 1:1 para um endpoint real (validado contra `danzeroum/Criptotrade@master`):

| Tela | Arquivo | Endpoint real | Módulo no repo |
|---|---|---|---|
| Visão Geral | screen_overview.jsx | GET /v1/metrics | core/metrics.py, core/ledger.py |
| Mercado | screen_market.jsx | GET /v1/market/* | analysis/* , agents/strategy_agent.py |
| Risco & Capital | screen_risk.jsx | GET /v1/risk/* | agents/risk_agent.py, safety/guardrails.py |
| Console HITL | screen_hitl.jsx | GET/PATCH /v1/orders | hitl/orders.py, hitl/config.py |
| Ordens | screen_orders.jsx | GET /v1/orders · /v1/trades/closed | api/routes/{orders,trades}.py |
| Agentes | screen_agents.jsx | GET /v1/agents | agents/registry.py |
| Diário | screen_journal.jsx | GET /v1/journal | api/routes/journal.py |
| Validação | screen_backtest.jsx | GET/POST /v1/backtest | api/routes/backtest.py |
| Observabilidade | screen_observability.jsx | GET /v1/process/events · /metrics | api/routes/process.py |
| Configurações | screen_settings.jsx | GET/PATCH /v1/hitl/config · /v1/config | hitl/config.py, core/config.py |

Layouts, componentes por tela, estados e critérios de aceite estão detalhados em `docs/` (especialmente Melhorias - Dashboard de Mercado e os dois Handoffs de telas). Não duplico aqui — os docs são a especificação.

## Interactions & Behavior
- **Navegação:** por estado React (`active` em app.jsx via `onNav`). ⚠️ Backlog S3: sincronizar com `location.hash` para deep-link. O botão "Ver no HITL" do Mercado depende disso (bug M2).
- **Botão "Como funciona de verdade"** (explain.jsx): FAB fixo em `bottom:22px; left:calc(var(--sidebar-w) + 22px)`; abre modal (scrim `rgba(20,24,28,.42)`, z-index 70) com: banner âmbar "Demonstração" (dados mockados) + passos numerados do pipeline real + endpoint + arquivos-fonte. Conteúdo por tela no objeto `EXPLAIN` — validado contra o repo; manter fiel ao backend ao portar.
- **Tooltips de descoberta** (tooltips.js): qualquer `[data-tip]` mostra balão no hover (delay 320ms, preferência acima, flip abaixo, clamp na viewport, some em scroll/click). Balão: fundo `#14181C`, texto `#F4F6F8`, 12px, max-width 264px, radius 8px, seta central. Todos os controles têm tip (sidebar, header, overlays do gráfico, HITL, filtros, salvar/rodar).
- **Estados de dados:** Visão Geral e Observabilidade têm seletor OK/Carregando/Vazio/Offline (padrão a generalizar — S1). Skeleton com shimmer, empty com CTA, error com retry.
- **HITL:** Aprovar/Rejeitar atualizam a fila com toast; rejeição pede motivo; cards de autonomia 0–3 clicáveis.
- **Tweaks (demo):** painel com densidade (confortável/compacta) e paleta daltônica.

## State Management
- `CT_PAIR` (par global) — hook `useCurrentPair` em components.jsx; header e métricas rebindam. ⚠️ Bug M1 (aberto de propósito no protótipo, documentado): a tela de Mercado ainda lê singletons `CT.*` e não rebinda ao par — corrigir na integração real indexando por par.
- Estado por tela é local (useState). Sem store global além do par.
- Ao integrar: cada tela troca seu mock pelo fetch do endpoint da tabela acima; `data_admin.js` (futuro, telas A1–A10) espelha esse padrão.

## Design Tokens (fonte: prototype/styles.css)
- **Cores:** bg `#F4F6F8` · surface `#FFFFFF` · surface-2 `#F6F8FA` · surface-3 `#EEF1F4` · border `#E4E8EC` · border-2 `#D5DAE0` · ink `#14181C` · ink-2 `#5B636C` · ink-3 `#8A929B` · ink-4 `#AEB5BD` · accent `#14181C` · up/ok `#0E9D6E` (bg `#E7F6EF`) · down/crit `#DC2B2B` (bg `#FCEAEA`) · warn `#C77F08` (bg `#FBF1DD`) · info `#2563EB` (bg `#E7EEFD`) · violet `#7C5CFC`
- **Tipografia:** IBM Plex Sans (UI, 400–700) · IBM Plex Mono (números/código, `font-variant-numeric: tabular-nums`). Base 14px; títulos de página 20px/600/-.02em; label-xs 10.5px uppercase +.06em.
- **Raios:** --r 9px · --r-lg 13px (cards) · pills 999px. **Sombras:** --sh-sm `0 1px 2px rgba(20,24,28,.05)` · --sh-pop (popovers). **Layout:** --sidebar-w 232px · --header-h 60px · gaps de grade 16px · card padding 18px (12px em densidade compacta).

## Assets
Nenhum binário — ícones são SVG inline (`ICON_PATHS` em components.jsx, stroke 24×24), gráficos são SVG gerados. Fontes via Google Fonts (IBM Plex).

## Ordem de execução sugerida (consolidada dos docs)
1. **Backend primeiro:** `Handoff Dev - Fechamento de Posições (Grid)` — destrava P&L/win-rate reais ("Sem dados" some). Design pronto, 5 passos incrementais, 0 testes existentes modificados.
2. **P0 do console:** M1 (rebind por par), M2 (Ver no HITL), M3/S1 (estados), S3 (deep-link) — em `Melhorias - Dashboard de Mercado`.
3. **Layout:** C4–C6 de `Validação de Layout - Mercado` (banda de sinal responsiva, breakpoints).
4. **Camada administrativa:** A1→A3→A9 primeiro (auth, RBAC, páginas de sistema), depois A4/A5/A7 — em `Handoff Dev - Telas Administrativas`.
5. ⚠️ **Antes de abrir issues do plano antigo:** o `master` já resolveu CT-002/004/005/006 e ORDER_ROUTING — ver seção "O master está à frente" em `Validação de Fidelidade`.

## Files
Todos listados na árvore acima. Entry point do protótipo: `prototype/Criptotrade Console.html`. Especificações: `docs/*.html`.
