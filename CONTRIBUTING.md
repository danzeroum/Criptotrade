# Contribuindo com o Criptotrade

Obrigado por contribuir! Este guia resume o fluxo de desenvolvimento. Para a
arquitetura, ver `docs/architecture/arquitetura.md` (C4) e
`docs/uml/arquitetura-uml.md` (classes); para o backlog priorizado, ver
`docs/plano-melhorias.md`.

## Princípios inegociáveis

Toda mudança **deve preservar** os invariantes centrais:

1. **Paper-trading-first** — `EXCHANGE_DRY_RUN` é obrigatório; o único caminho
   para a exchange roda offline por padrão (ADR-001). Nunca introduza um caminho
   de ordem real que rode sem override explícito de ambiente.
2. **HITL fail-closed** — ordens acima do limiar de autonomia exigem aprovação
   humana; em produção a API sobe fail-closed sem `API_KEYS`.
3. **Tudo auditável** — decisões e execuções vão para o ledger append-only / event
   log XES. Não remova trilha de auditoria.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q                       # suíte completa (ver contagem no README/TESTING.md)
```

Console React (opcional): `cd docs/design/pages && npm install && npm run build`.

## Fluxo

1. **Branch** a partir de `master`.
2. **Commits** em [Conventional Commits](https://www.conventionalcommits.org/)
   (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `build:`, `chore:`).
3. **Testes**: adicione/estenda testes em `tests/`. O gate de cobertura da CI é
   **72%** (`pyproject.toml`); não o reduza.
4. **Lint**: `ruff check src` (regras E4/E7/E9/F).
5. **CI verde** antes do merge — jobs `test`, `console-build`, `console-e2e`,
   `docker-build`, `validate-phases`, `secret-scan`.
6. **PR** contra `master`. Decisões arquiteturais entram como **ADR** em
   `docs/adr/` (use `ADR-Template.md`; próximo número livre indicado no
   `docs/adr/README.md`).

## Convenções

- **Sem segredos no repo.** `.env` é gitignored; use `.env.example` como
  referência. A CI roda `secret-scan` e `scripts/validate_deploy_config.py`.
- **Nomes de classe únicos por propósito** (ver R2 em `arquitetura.md §12`):
  evite reintroduzir colisões como dois `SquadOrchestrator`.
- **Reuse antes de criar**: cheque utilitários existentes em `src/core`,
  `src/utils` e (no front) `components.jsx` antes de escrever novos.
- **Documentação viva vs. histórica**: atualize os docs de estado atual
  (`README`, `TESTING.md`, `mapeamento-dados.md`, `arquitetura.md`,
  `plano-melhorias.md`, `CHANGELOG.md`). **Não** reescreva registros datados
  (roadmaps por sprint, auditorias) — eles são snapshots históricos.

## Reportando vulnerabilidades

Ver `SECURITY.md`.
