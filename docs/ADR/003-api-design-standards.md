# ADR-003 — Padrões de Design da API

## Status
Aceita (2025-09-25)

## Contexto
Para garantir consistência, DX e manutenção, a API do BuildToValue v6 deve seguir convenções REST claras com versionamento explícito e documentação de contrato.

## Decisão
- **URLs RESTful** com substantivos no plural (ex.: `/users`, `/orders`).
- **Versionamento obrigatório**: prefixo `/api/v1/`.
- **Métodos HTTP semânticos**: GET (leitura), POST (criação), PUT/PATCH (atualização), DELETE (remoção).
- **Status HTTP consistentes** e **OpenAPI com exemplos** (request/response + erros `application/problem+json`).

## Alternativas Consideradas
- GraphQL (flexível, porém extrapola o MVP e complica os gates).
- API sem versionamento (risco de breaking changes em evolução).

## Consequências
- **Positivas:** menos ambiguidade, melhor DX, facilita automação dos gates.
- **Negativas:** exige validação contínua dos contratos em PRs.

## Validação
- Gate automatizado em `scripts/gates-v6.sh`:
  - Verifica prefixo `/api/vX/` na OpenAPI.
  - Heurística contra verbos nos caminhos.
  - YAML bem-formado.

## Referências
- OpenAPI Specification
- REST API Design Rulebook
