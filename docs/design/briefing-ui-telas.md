# Briefing de UI — Conectar Frontend ↔ Backend (todas as telas e configurações)

> Para o(a) designer. Objetivo: especificar **todas** as telas do console para cobrir
> 100% das funcionalidades e configurações da API. Cada elemento abaixo aponta para
> um **endpoint real** e **campos reais** — nada é inventado.

## 0. Fontes de verdade (consultar antes de desenhar)
- **Contrato da API:** `docs/design/pages/openapi.json` + `openapi.d.ts` (tipos gerados).
  São os **nomes de campos exatos**. O CI falha se a UI/contrato divergirem (gate P3‑4) — então
  **não invente campos**: se precisar de um campo que não existe, marque como *gap de backend*.
- **Design system:** `docs/design/pages/styles.css` (tokens) + `components.jsx` (biblioteca).
- **App:** React "classic scripts" (sem bundler), telas trocadas por **hash routing** (`#market`, `#risk`…).
  UI primária = console React (`docs/design/pages/`). UI secundária/operacional = Streamlit (`src/dashboard/app.py`).
- **Base da API:** envelope `APIResponse<T>` → `{ data, _links?, error?, message? }`. Auth opcional via header `X-API-Key`.

---

## 1. Design System — REUSAR, não recriar

### 1.1 Tokens (de `styles.css :root`)
| Grupo | Tokens |
|---|---|
| Superfícies | `--bg #F4F6F8` · `--surface #FFF` · `--surface-2 #F6F8FA` · `--surface-3 #EEF1F4` · `--border #E4E8EC` |
| Texto (ink) | `--ink #14181C` · `--ink-2 #5B636C` · `--ink-3 #8A929B` · `--ink-4 #AEB5BD` |
| Semânticas | `--up #0E9D6E` (alta/positivo) · `--down #DC2B2B` (baixa/erro) · `--warn #C77F08` · `--info #2563EB` · `--violet #7C5CFC` (+ variantes `-bg`/`-line`) |
| Acento | `--accent #14181C` / `--accent-ink #FFF` |
| Raios | `--r-sm 6` · `--r 9` · `--r-lg 13` · `--r-pill 999` |
| Sombras | `--sh-sm` · `--sh` · `--sh-lg` · `--sh-pop` |
| Tipografia | `--sans 'IBM Plex Sans'` · `--mono 'IBM Plex Mono'` (números/preços sempre em mono) |
| Layout | `--sidebar-w 232px` · `--header-h 60px` (52 no breakpoint menor) |

### 1.2 Biblioteca de componentes (de `components.jsx` — usar estes)
| Componente | Para quê | Props‑chave |
|---|---|---|
| `Icon` | ícones SVG por nome | `name` (alert, check, x, trending, bar, activity, settings, shield, clock, book, bell, zap, refresh, user, dollar, eye, play, stop, plus, candle, list), `size` |
| `Card` | contêiner padrão | `title, icon, action, children` |
| `Badge` | status/pílula | `variant` (ok/down/warn/neutral/info), `dot` |
| `Btn` | botão | `variant` (ghost/…), `size` (sm), `disabled` |
| `KPI` | tile de métrica | `label, value, sub, icon, delta, format` (plain/pct/pct_direct/usd/int) |
| `Meter` | barra de progresso c/ limiares | `value, max, warn, crit` |
| `Seg` | segmented control (ex.: timeframe) | `options, value, onChange` |
| `Tabs` | abas | `tabs, active, onChange` |
| `NumField` / `SliderField` | input numérico / slider (formulários de config) | `label, value, onChange, min, max, step, unit` |
| `LoadingState` / `EmptyState` / `ErrorState` | **estados honestos** | `label` / `message, onRetry` |

### 1.3 Regra de ouro — estados honestos (UX P0)
Toda área que busca dados deve desenhar **4 estados**, nunca um `--` ambíguo:
1. **Loading** → `LoadingState` ("Carregando…")
2. **Empty** (sem histórico) → `EmptyState` ("Sem dados" + dica)
3. **Error/Offline** (API caiu / 5xx) → `ErrorState` ("API offline" + "Tentar novamente")
4. **OK** → conteúdo. Métricas sem amostra suficiente vêm como `null` no backend → renderizar "Sem dados", **não** `0`.

### 1.4 Shell (de `shell.jsx`/`app.jsx`)
- **Sidebar** (esq, 232px): logo + 8 itens de nav + **badge de pendentes** no item HITL.
- **Header** (topo): par selecionado + **preço/variação 24h reais** (`/market/{pair}/ticker`), nível HITL, status de saúde, sino de alertas.
- **Content**: `ErrorBoundary` por tela + animação `screen-enter`.
- **Alert Drawer** (direita, sob demanda): histórico + **SSE em tempo real**.
- **Toasts**: alertas `critical`/`high` viram toast.
- **Seletor global de par** (`window.CT_PAIR`): o seletor do Mercado e o header já compartilham via evento `ct:pair` + `localStorage`. **Qualquer tela "por moeda" deve plugar nesse store** (não criar seletor isolado).

---

## 2. Mapa de navegação (atual + proposto)
Atual (8): **HITL · Ordens · Agentes · Risco · Mercado · Diário · Backtest · Config**.
**Adicionar (gaps):** **Visão Geral/Portfólio** (headline de métricas) e **Observabilidade** (process events). Edição de **config de agentes** dentro de Agentes.

---

## 3. Especificação por tela
Legenda: 🟢 já conectado · 🟡 parcial · 🔴 gap (desenhar).

### 3.1 🔴 Visão Geral / Portfólio (NOVA — maior gap)
**Por quê:** os KPIs de performance (Sharpe, Win Rate, Drawdown, P&L, valor do portfólio) hoje só existem no Streamlit — o console React **não tem tela de overview**.
- **`GET /v1/metrics?period=&symbol=`** → `sharpe_ratio, win_rate, max_drawdown, profit_factor, total_trades, open_positions, portfolio_value_usdt, pnl_period_usdt, pnl_period_pct, exposure_pct, has_data`. Campos de ratio podem ser `null` → "Sem dados".
- **`GET /v1/metrics/equity?period=&symbol=`** → série `[{t, equity, drawdown}]` para a **curva de capital** (usar `CandleChart`/área).
- **`GET /v1/orders?limit=`** → tabela de últimas ordens.
- **Controles:** `Seg` de período (1d/7d/30d/90d/all) + **seletor de par global** (KPIs por moeda usando `?symbol=`, "Todos" = portfólio). Linha de KPIs (`KPI` tiles) + curva de equity + drawdown.

### 3.2 🟢 HITL Controls (`#hitl`)
Aprovação humana das ordens dentro do nível de autonomia.
- **`GET /v1/hitl/config`** → `current_level, min_level, max_level, level_description, levels[], pending_orders_count`.
- **`GET /v1/orders?status=pending`** → fila de aprovação (`pair, side, quantity, notional, confidence, reason`).
- **`PATCH /v1/orders/{id}/status`** → `{ decision: "approve"|"reject", operator_note?, operator }`. **Nota obrigatória ao rejeitar** (validação 422). 
- **`PATCH /v1/hitl/config`** → `{ level, reason, operator }` (slider de nível 0–3 + motivo).
- **Estados:** card por ordem pendente com Aprovar/Rejeitar; confirmar ação (é financeira).

### 3.3 🟢 Ordens (`#orders`)
Ciclo completo das ordens.
- **`GET /v1/orders?limit=&offset=&status=`** → tabela paginada (`id, pair, side, quantity, notional, status, operator_id, created_at`). Ícones por status (pending/approved/filled/rejected/cancelled).
- **`POST /v1/orders`** → criação manual (se exposto na UI). 
- **Melhorar:** filtro por **par** (plugar no seletor global; hoje o Streamlit filtra no cliente). Filtros: status + paginação.

### 3.4 🟡 Agentes (`#agents`)
- **`GET /v1/agents`** → `[{id, description, domain, status, implemented, cycles, last_action_at}]`. Tabela + ícone de status + badge stub.
- 🔴 **Editar parâmetros (gap):** **`GET/PATCH /v1/agents/{id}/config`** (`{params:{…}}`) — os métodos existem no client mas **nenhuma tela edita**. Desenhar um **drawer/modal "Configurar agente"** por linha, com `NumField`/`SliderField` por parâmetro + Salvar.
- Detalhe por agente: `GET /v1/agents/{id}` (sem método ainda — *gap menor*).

### 3.5 🟢 Risco (`#risk`)
- **`GET /v1/risk/protections`** → proteções ativas (position size, stop, daily loss…).
- **`GET /v1/risk/circuit-breaker`** → estado do disjuntor (aberto/fechado, perdas consecutivas, perda diária).
- **`GET /v1/risk/kelly`** → sizing de Kelly (pode vir "insuficiente" → "Sem dados").
- **`GET /v1/metrics/equity`** → curva de drawdown.
- 🔴 **Editar (gap parcial):** **`PATCH /v1/risk/config`** existe e é usado na tela Config — considerar atalho de edição aqui também.

### 3.6 🟢 Mercado (`#market`) — referência de tela "por moeda"
- **Seletor de par** (`<select>` ← `GET /v1/market/pairs`) + `Seg` de timeframe. **Já plugado no store global.**
- **`GET /v1/market/{pair}/ticker`** → `last, change_24h_pct, high_24h, low_24h` (KPI "Variação 24h" + header).
- `candles, indicators, regime, levels, volume-profile, patterns, signal` → gráfico de candles, indicadores (RSI/MACD/BB/ATR/EMAs/Stoch/OBV/Vol), S/R + Fibonacci, Volume Profile, padrões, **box de Sinal** (entry/stop/alvo/RR/tamanho/confiança).
- *Obs.:* o explicador dos 4 regimes ainda usa mock (`CT.regime.options`) — decorativo; o regime ativo é real.

### 3.7 🟢 Diário (`#journal`)
- **`GET /v1/journal`** + **`GET /v1/journal/metrics`** → entradas + métricas comportamentais.
- **`POST /v1/journal`** → nova entrada (formulário).

### 3.8 🟢 Backtest (`#backtest`)
- **Seletor de par** (← `/v1/market/pairs`; agora o backend **respeita** o par — antes ignorava). Unificar o visual com o seletor do Mercado.
- **`POST /v1/backtest/run`** (assíncrono → `job_id`) + **polling `GET /v1/backtest/jobs/{id}`** (running/done/error).
- **`POST /v1/backtest/montecarlo`** e **`/walkforward`** (síncronos). Body: `{ strategy, pair, initial_capital, commission_pct, slippage_bps, monte_carlo_sims }`.
- Resultados: KPIs (trades, win rate, pnl, drawdown, sharpe, profit factor, expectancy), histograma Monte Carlo, folds walk‑forward.

### 3.9 🟢/🟡 Configurações (`#settings`) — **todas as configs num lugar**
Ver §4. Hoje conecta `/config`, `/risk/config`, `/alerts/config`; falta `/agents/{id}/config` (§3.4) e read‑back de alerts.

### 3.10 🔴 Observabilidade / Process (NOVA)
- **`GET /v1/process/events`** → eventos de ciclo do orquestrador (XES: `agent_cycle_started/completed/failed`). **Nenhuma UI hoje.**
- Desenhar uma **timeline/tabela** de ciclos (duração, agentes que rodaram, falhas) — fecha o loop de "o loop está rodando?".

### 3.11 🟢 Alertas (drawer global)
- **`GET /v1/alerts/history?limit=`** + **SSE `GET /v1/alerts`** (tempo real). Itens: `severity, type, message, occurred_at, pair, auto_action`.
- 🔴 **`PATCH /v1/alerts/config`** é **write‑only** (sem GET): o formulário precisa de defaults/placeholders (marcar como *gap de read‑back* no backend).

---

## 4. Configurações — visão consolidada (todos os `PATCH`)
A tela **Config** deve cobrir, em seções com `Card` + `NumField`/`SliderField`/`Seg`:
| Seção | Endpoint | Campos editáveis (ver `.d.ts`) | Observação |
|---|---|---|---|
| Sistema/Trading | `GET/PATCH /v1/config` | exchange, dry_run, capital, intervalo, autonomia, app_env | alguns read‑only em prod |
| Autonomia (HITL) | `GET/PATCH /v1/hitl/config` | `level` (0–3) + `reason`, `operator` | também no Header/HITL |
| Risco | `GET/PATCH /v1/risk/config` | limites de position/stop/daily‑loss, RR mínimo | validar ranges |
| Agentes (por agente) | `GET/PATCH /v1/agents/{id}/config` | `params{}` dinâmicos | **gap de UI** (§3.4) |
| Alertas | `PATCH /v1/alerts/config` | limiares/severidade | **sem GET** (defaults) |
Regras: validar ranges no cliente (espelhar o backend), **confirmar** mudanças sensíveis (autonomia/risco/dry_run), feedback de sucesso/erro (toast), `operator` sempre enviado.

---

## 5. Gaps priorizados (o que falta conectar)
1. **P1 — Visão Geral/Portfólio:** `GET /v1/metrics` (+`?symbol`) e `/equity` não têm casa no React (só Streamlit). Headline de performance ausente.
2. **P1 — Editar config de agentes:** `GET/PATCH /v1/agents/{id}/config` sem UI.
3. **P2 — Observabilidade:** `GET /v1/process/events` sem UI.
4. **P2 — Métricas por moeda no console:** o novo filtro `?symbol=` (já usado no Streamlit) deve aparecer na Visão Geral/Ordens via seletor global.
5. **P3 — Read‑back de alertas:** `PATCH /v1/alerts/config` sem `GET` (defaults no form; idealmente expor GET no backend).
6. **P3 — `POST /v1/orders` e `GET /v1/agents/{id}`:** sem método/superfície no client.

---

## 6. Regras transversais (valem para todas as telas)
- **Contrato:** campos exatos do `openapi.d.ts`. Campo inexistente = gap de backend (não inventar).
- **Estados honestos:** Loading/Empty/Error/Offline sempre (§1.3); `null` ≠ `0`.
- **Idioma:** PT‑BR; números/preços em fonte **mono**; moedas com casas adequadas (XRP ≠ BTC).
- **Seletor de par:** único e global (store `CT_PAIR`) — header, Mercado, Visão Geral, Ordens, Backtest compartilham.
- **Ações financeiras/destrutivas** (aprovar/rejeitar ordem, mudar autonomia/risco): **confirmação** + feedback.
- **Segurança:** todas as chamadas mutáveis enviam `X‑API‑Key` quando configurado (já no `apiClient`).
- **Modo mock:** `window.USE_MOCK_DATA=true` renderiza dados mock sem backend (usado no e2e) — toda tela deve ter fallback mock que não quebra.
- **Responsivo:** sidebar colapsável < ~960px; grids de KPI de 5→2→1 colunas.
- **Acessibilidade:** `aria-label` em selects/botões‑ícone; contraste AA (a paleta já atende).

---

### Resumo do que mudou recentemente (contexto p/ o designer)
Multi‑cripto foi entregue no backend e parcialmente no frontend: **seletor de par no Mercado + header reflete**, endpoints `/market/pairs` e `/market/{pair}/ticker`, métricas e backtest **por símbolo**, e seletor no Streamlit. O que **falta no console React** está em §5 — priorizar a **Visão Geral/Portfólio** e a **edição de config de agentes**.
