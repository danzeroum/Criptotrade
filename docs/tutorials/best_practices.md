# Melhores Práticas para Construir Agentes de IA com BuildToValue v6.1

## Introdução

Construir agentes de IA robustos vai além de simplesmente escrever código funcional. Este guia aborda as melhores práticas de engenharia de software aplicadas ao desenvolvimento de agentes, alinhadas com a metodologia **BuildToValue v6.1**. Os pilares são: Modularidade, Testabilidade, Escalabilidade e Segurança.

## 1. Modularidade (Princípio da Responsabilidade Única)

Mantenha a lógica de cada agente ou componente focada e especializada. Um agente que faz tudo é difícil de manter, depurar e escalar.

* **Padrões Relacionados:** `Multi-Agent Collaboration`, `Prompt Chaining`.

```python
# Exemplo de modularidade: Cada chain tem uma única responsabilidade.

# Agente de Extração (Especialista em extrair dados)
extract_chain = LLMChain(...)

# Agente de Resumo (Especialista em resumir os dados extraídos)
summarize_chain = LLMChain(...)

# Orquestração limpa com SimpleSequentialChain
full_chain = SimpleSequentialChain(chains=[extract_chain, summarize_chain], verbose=True)
```

## 2. Testabilidade (Validação Contínua)

Um agente só é confiável se o seu comportamento for testável. Crie testes automatizados para cada componente e para a sua integração.

* **Padrões Relacionados:** Evaluation and Monitoring.

```bash
# Na sua pipeline de CI/CD, os Quality Gates validam o seu agente.
# Exemplo de comando no seu script `gates-v6.sh`:

# Testa a lógica de extração de forma isolada (unitário)
pytest tests/unit/test_extract_chain.py

# Testa o pipeline completo de ponta a ponta (integração)
./scripts/test-integration-nfe-processor.sh
```

## 3. Escalabilidade (Planejamento para o Futuro)

Projete os seus agentes para serem eficientes em termos de recursos, garantindo que possam lidar com um aumento de carga.

* **Padrões Relacionados:** Parallelization, Resource-Aware Optimization.

```python
# Use Parallelization para tarefas independentes e reduzir a latência.
from langchain.schema.runnable import RunnableParallel

parallel_chain = RunnableParallel(
    extraction=extract_chain,
    sentiment_analysis=sentiment_chain # Outro especialista a trabalhar em paralelo
)

# A execução paralela otimiza o uso de recursos.
result = parallel_chain.invoke({"document": "Texto longo..."})
```

## 4. Segurança (Construindo com Confiança)

A segurança não é uma funcionalidade, é um requisito. Implemente defesas em camadas para garantir que o seu agente opere dentro de limites éticos e seguros.

* **Padrões Relacionados:** Guardrails, Human-in-the-Loop, Exception Handling.

```python
# Exemplo de um Guardrail de entrada e um HITL de saída

def input_guardrail(input_text: str) -> str:
    """Um Guardrail simples para validar inputs e prevenir injeções de prompt."""
    FORBIDDEN_PHRASES = ["ignore todas as instruções anteriores", "esqueça as regras"]
    if any(phrase in input_text.lower() for phrase in FORBIDDEN_PHRASES):
        raise ValueError("Input bloqueado por violação de segurança (tentativa de injeção).")
    return input_text


def human_in_the_loop_review(response: str) -> str:
    """Simula um ponto de verificação onde uma ação crítica requer aprovação humana."""
    # Em um sistema real, isso poderia enviar uma notificação para uma interface humana.
    print(f"\n[HITL] Ação proposta pelo agente: '{response}'")
    approval = input("Aprovar esta ação? (s/n): ")
    if approval.lower() == 's':
        return "✅ Ação Aprovada pelo Humano."
    else:
        return "❌ Ação Rejeitada pelo Humano."


# Fluxo de uso
try:
    user_input = "Envie um email para todos os clientes com a nova promoção."
    validated_input = input_guardrail(user_input)
    
    # ... lógica do agente para gerar a ação ...
    proposed_action = f"Enviar email em massa: '{validated_input}'"
    
    review_status = human_in_the_loop_review(proposed_action)
    print(review_status)

except ValueError as e:
    print(f"Erro de Segurança: {e}")
```

## Conclusão

Adotar estas melhores práticas garante que os seus agentes de IA sejam não apenas eficazes, mas também modulares, confiáveis, escaláveis e seguros, cumprindo a promessa da filosofia Crisp Pragmatist.
