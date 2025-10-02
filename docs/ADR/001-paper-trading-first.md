# ADR-001: Paper Trading First Strategy

## Status
✅ **Aceita** (2025-10-02)

## Contexto
O projeto visa criar uma plataforma de trading automatizada com IA. Existe tensão entre:
- Necessidade de validar estratégias sem risco real
- Urgência de testar em condições de mercado reais
- Restrições orçamentárias (capital limitado para testes)

## Decisão
**Implementar OBRIGATORIAMENTE em modo "Paper Trading" durante todo o MVP (fase 1).**

Características do Paper Trading:
- Simular ordens sem executá-las em exchanges reais
- Usar API testnet das exchanges quando disponível
- Registrar todas as "operações" no ledger como se fossem reais
- Calcular P&L baseado em preços reais de mercado
- Validar TODAS as capacidades dos agentes antes de live trading

## Alternativas Consideradas

### 1. **Live Trading Imediato com Capital Mínimo**
- **Prós:** Teste em condições reais desde dia 1
- **Contras:** 
  - Alto risco de perda de capital
  - Pressão emocional durante desenvolvimento
  - Dificuldade de debug com dinheiro real
  - Violação do princípio de segurança first
- **Rejeição:** Não alinhado com foundation "lite" de baixo risco

### 2. **Backtesting Apenas (sem paper trading)**
- **Prós:** Zero risco, rápido para testar
- **Contras:**
  - Não valida latência de execução
  - Não testa integração com APIs reais
  - Histórico não captura "market impact"
  - Overfitting de estratégias
- **Rejeição:** Insuficiente para validar sistema real

### 3. **Paper Trading → Escolhida**
- **Prós:**
  - Zero risco financeiro durante desenvolvimento
  - Validação realista de latência e APIs
  - Permite iterar rápido sem medo
  - Possibilita debug completo de agentes
  - Alinhado com "safety first" da metodologia
- **Contras:**
  - Não captura slippage real
  - Ausência de pressão emocional (psicológica)
- **Mitigações:** 
  - Adicionar "slippage simulado" (0.1-0.5%)
  - Implementar métricas conservadoras de sucesso

## Consequências

### Positivas
- ✅ Desenvolvimento seguro e iterativo
- ✅ Validação completa de agentes sem risco
- ✅ Possibilidade de testar múltiplas estratégias em paralelo
- ✅ Redução de stress durante desenvolvimento
- ✅ Ledger de decisões auditável desde dia 1

### Negativas
- ⚠️ Transição para live trading precisará de fase de validação adicional
- ⚠️ Possível falsa confiança se métricas forem muito otimistas
- ⚠️ Necessidade de re-testar comportamento psicológico com capital real

### Mitigações
- Adicionar "friction realista" ao paper trading (slippage, fees, latência)
- Definir KPIs conservadores para transição (Sharpe > 1.5, Drawdown < 10%)
- Criar ADR separado para critérios de "go-live"
- Manter paper trading em paralelo mesmo após live (A/B testing)

## Critérios de Transição para Live Trading

**OBRIGATÓRIOS (todos devem ser atendidos):**
1. ✅ Sharpe Ratio > 1.5 em 3 meses de paper trading
2. ✅ Max Drawdown < 10% do capital simulado
3. ✅ Win Rate > 55% com no mínimo 100 trades
4. ✅ Zero violações de guardrails em 1 mês
5. ✅ Uptime > 99.5% em 1 mês
6. ✅ HITL approval workflow validado
7. ✅ Ledger auditado e aprovado
8. ✅ Testes de segurança (penetration testing) concluídos
9. ✅ Progressive Autonomy funcionando (L1→L2)
10. ✅ Capital real alocado >= $5,000

**RECOMENDADOS:**
- 📊 Backtesting adicional com 2+ anos de dados históricos
- 🧪 Stress testing com cenários de alta volatilidade
- 🔐 Seguro ou stop-loss de portfólio ativado
- 📱 Sistema de alertas críticos via Telegram

## Validação

- [x] Arquiteto aprovou (confidence 0.95)
- [x] Developer aprovou (confidence 0.9)
- [x] Auditor aprovou (confidence 0.85) 
- [x] Ops aprovou (confidence 1.0)
- [x] Consenso: Unânime

## Referências
- BuildToValue v6.1 - Safety First principles
- Discovery consensus: "baixo custo e baixo risco"
- Decision tree: Foundation level "lite"

---
**Última Atualização:** 2025-10-02  
**Próxima Revisão:** Após 1 mês de paper trading
