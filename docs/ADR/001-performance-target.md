# ADR-001: Meta de Performance para MVP

## Status
Aceita (2025-01-20)

## Contexto
BuildToValue v6 precisa definir uma meta de performance pragmática para MVPs que equilibre:
- Simplicidade de implementação
- Experiência aceitável do usuário
- Vendabilidade do produto
- Evitar over-engineering prematuro

## Decisão
Adotar **P95 < 800ms** como meta de performance para MVP (fase lite).

## Alternativas Consideradas
1. **P95 < 500ms**: Meta da v5, muito agressiva para MVP
2. **P95 < 1000ms**: Pode comprometer UX
3. **P95 < 800ms**: Equilibra pragmatismo e qualidade

## Consequências
### Positivas
- Permite foco em features vs otimização
- Reduz complexidade inicial
- Time-to-market mais rápido

### Negativas
- Precisará otimização para standard/enterprise
- Pode limitar alguns use cases

### Mitigações
- Monitorar métricas desde o início
- Planejar otimizações incrementais
- Usar cache strategy desde MVP

## Validação
- [x] Arquiteto aprovou
- [x] Dev team concordou
- [x] Ops validou viabilidade
