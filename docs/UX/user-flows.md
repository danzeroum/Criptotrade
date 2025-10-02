# 🧭 Fluxos de Usuário

## Onboarding
1. Usuário acessa landing page BuildToValue v6.
2. Visualiza indicador de mock data quando aplicável.
3. Realiza cadastro básico com campos marcados e validações acessíveis.
4. Recebe confirmação com toast `success` e traceId visível nos logs.

## Dashboard Operacional
1. Login seguro com feedback de estado do botão.
2. Carregamento das métricas principais (P95, throughput, erros).
3. Acesso rápido aos checklists obrigatórios.
4. CTA para rodar demo (`./scripts/demo-v6.sh`) com indicação `X-BTF-Mock`.

## Gestão de ADRs
1. Navegação para seção de governança.
2. Visualização do ledger com filtros por evento.
3. Abertura de novo ADR usando template padronizado.
4. Registro automático no `.BuildToValue/ledger/decisions.log`.
