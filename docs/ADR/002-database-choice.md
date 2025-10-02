# ADR-002: Escolha do Banco de Dados

## Status
Proposta

## Contexto
A metodologia BuildToValue v6 exige uma base de dados relacional confiável para suportar transações críticas e métricas de observabilidade. A decisão deve equilibrar facilidade de operação, custo e compatibilidade com o stack padrão Spring Boot.

## Decisão
Utilizar **PostgreSQL 15** como banco de dados primário para os ambientes lite e standard. Para enterprise, complementar com réplicas e recursos avançados conforme necessidade.

## Alternativas Consideradas
1. **MySQL**: ampla adoção, porém tooling menos alinhado aos requisitos de JSON e extensões geoespaciais.
2. **SQL Server**: robusto, mas custos mais altos e menor alinhamento com o ecossistema open source proposto.
3. **PostgreSQL**: suporte a extensões, JSONB, ótimo custo-benefício e compatibilidade com ferramentas DevOps adotadas.

## Consequências
### Positivas
- Comunidade ativa e suporte amplo
- Facilidade de integração com Spring Data JPA
- Compatível com estratégias de replicação e HA

### Negativas
- Requer tunning para workloads de alta concorrência
- Necessidade de monitoramento ativo de vacuum/autovacuum

### Mitigações
- Configurar alertas via módulo de monitoring do Terraform
- Documentar boas práticas de manutenção no handoff

## Validação
- [ ] Arquiteto aprovou
- [ ] Dev team concordou
- [ ] Ops validou viabilidade
