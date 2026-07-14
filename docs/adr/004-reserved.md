# ADR-004: Número reservado (não utilizado)

## Status
⬜ Vago — número não utilizado

## Contexto
A numeração dos ADRs é sequencial. Durante a consolidação dos três diretórios ADR
antigos (`docs/ADR/`, `docs/ADRs/`, `docs/adr/`) o número **004** não foi atribuído
a nenhuma decisão: o histórico saltou de **ADR-003** (persistência SQLite WAL) para
**ADR-005** (caminho de escalabilidade).

Este arquivo existe apenas para **tornar o salto explícito** — evita que um leitor
futuro conclua que um ADR-004 foi perdido ou removido silenciosamente.

## Decisão
Não reutilizar o número **004** retroativamente. O próximo ADR novo deve usar
**006** (o maior número em uso é 005). Se uma decisão couber tematicamente entre a
003 e a 005, documente-a com o próximo número livre e faça referência cruzada, em
vez de preencher o 004.

## Consequências
- A sequência de ADRs fica navegável e auditável, sem lacuna inexplicada.
- Nenhuma decisão de arquitetura é implicada por este placeholder.

## Referências
- `docs/adr/README.md` (índice), ADR-003, ADR-005.
