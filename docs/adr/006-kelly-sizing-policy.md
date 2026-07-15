# ADR-006: Política de sizing por Kelly (fonte única + cauda de integração)

## Status
🟡 Aceita parcialmente (2026-07-15) — fonte única entregue; sizing ao vivo diferido.

## Contexto
O módulo `src/risk/` (`KellyCriterion`, `PositionSizer`, `CapitalProtections`)
existia **completo e testado, mas morto**: nenhum código de aplicação o
importava. Pior, o endpoint `GET /v1/risk/kelly` **reimplementava o Kelly inline**
(`src/api/routes/risk.py`), com constantes e fórmulas divergentes da biblioteca —
dando a falsa impressão de que o sistema dimensionava posições por Kelly quando, na
verdade, o pipeline de trading (`SquadOrchestrator._position_quantity`) usa
`position_size_pct` fixo. Isto está registrado como **R5** em
`docs/architecture/arquitetura.md §12` e no §8 de `docs/data/mapeamento-dados.md`.

Havia três caminhos possíveis: (a) **deletar** o módulo morto; (b) **unificar**
tornando a biblioteca a fonte única e o endpoint um consumidor; (c) **plugar** o
Kelly no sizing real das ordens.

## Decisão
Adotar (b) agora, de forma **preservadora de contrato**, e diferir (c):

1. A fórmula central do Kelly foi extraída para
   `src/risk/position_sizing.full_kelly_fraction(win_rate, avg_win_pct,
   avg_loss_pct)` — **fonte única de verdade**. É algebricamente idêntica à forma
   anterior (`(p·b − q)/b ≡ p − (1−p)/b`), então **nenhum número da API muda**.
2. `GET /v1/risk/kelly` passa a **delegar** a essa função (removendo a
   reimplementação inline). `KellyCriterion.full_kelly()` também a consome. Assim
   `src/risk/` deixa de ser código morto.
3. A apresentação do endpoint (Kelly fracionado × 0.25, risco de ruína, limiar de
   10 trades para `data_quality:"insufficient"`) é **mantida como está** — é um
   endpoint **consultivo** (display), não de execução.

## Diferido (cauda do R5)
- **Plugar `PositionSizer`/`KellyCriterion` no sizing real** de ordens
  (`SquadOrchestrator._position_quantity`) muda **o que é negociado** — é uma
  mudança de comportamento que exige validação dedicada (backtest comparativo,
  revisão de risco) e **não** entra junto de higiene de código.
- **Unificar a apresentação fracionada/ruína** entre endpoint e biblioteca (hoje o
  endpoint usa fração crua não-clampada; a lib usa percentual clampado [0.5, 5.0] e
  a fórmula clássica de ruína). Decisão de produto sobre qual semântica é canônica.
- **`CapitalProtections`** (limites diário/semanal/mensal com `size_multiplier`)
  permanece disponível, ainda não alimentado por P&L do período.

## Consequências
- **Positivas:** remove a duplicação e a falsa impressão; `src/risk/` passa a ser
  exercitado pela API; caminho claro para o sizing por Kelly quando houver
  validação. Zero mudança observável de contrato/comportamento.
- **Negativas:** o sistema **ainda não dimensiona por Kelly** — o valor pleno do
  R5 (sizing dinâmico por edge) fica para a etapa (c). O módulo continua
  parcialmente subutilizado (`PositionSizer`/`CapitalProtections`).

## Referências
- `docs/architecture/arquitetura.md §12` (R5), `docs/data/mapeamento-dados.md §8`.
- `src/risk/position_sizing.py`, `src/api/routes/risk.py`,
  `src/orchestration/squad_orchestrator.py` (`_position_quantity`).
- `docs/plano-melhorias.md` (R5 — backlog estrutural).
