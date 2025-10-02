# Getting Started: O Seu Primeiro Agente com BuildToValue v6.1

## Introdução

Bem-vindo ao guia prático da metodologia **BuildToValue v6.1 – Reality Check**. Este tutorial foi desenhado para ser a sua primeira experiência no campo de batalha, guiando-o na construção de um agente básico que já utiliza duas capacidades da família de **Execução de Tarefas**: `Prompt Chaining` e `Routing`.

Lembre-se da nossa filosofia: **disciplina mínima, valor máximo**. Vamos escrever código funcional primeiro.

## Passo 1: Configuração do Ambiente ( < 5 minutos)

1.  **Clone o repositório base**:
    ```bash
    git clone https://github.com/BuildToValue/template-v6.1-reality-check.git my-first-agent
    cd my-first-agent
    ```

2.  **Configure as variáveis de ambiente**:
    Copie o template `.env.template` para `.env` e adicione a sua chave de API da OpenAI.
    ```bash
    cp .env.template .env
    nano .env # Adicione sua OPENAI_API_KEY
    ```

3.  **Inicie os serviços (se necessário)**:
    Se o seu projeto necessitar de serviços externos como bases de dados, pode iniciá-los com Docker.
    ```bash
    # Exemplo: docker-compose up -d
    ```

## Passo 2: Implementando `Prompt Chaining`

O `Prompt Chaining` permite-nos quebrar uma tarefa complexa em um pipeline de passos mais simples e gerenciáveis.

```python
# Crie um arquivo chamado: getting_started_chaining.py

from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain, SimpleSequentialChain
from langchain.prompts import PromptTemplate
import os
from dotenv import load_dotenv

# Carrega a chave de API do arquivo .env
load_dotenv()

# Configuração do LLM
llm = ChatOpenAI(temperature=0.1, model_name="gpt-4")

# Chain 1: Extrair informações chave
extract_prompt = PromptTemplate(
    input_variables=["document"],
    template="Extraia as 3 informações principais deste documento: {document}"
)
extract_chain = LLMChain(llm=llm, prompt=extract_prompt, output_key="key_points")

# Chain 2: Gerar resumo com base nas informações extraídas
summarize_prompt = PromptTemplate(
    input_variables=["key_points"],
    template="Com base nestes pontos principais: {key_points}, gere um resumo conciso."
)
summarize_chain = LLMChain(llm=llm, prompt=summarize_prompt, output_key="summary")

# Encadeamento completo: a saída de `extract_chain` alimenta `summarize_chain`
full_chain = SimpleSequentialChain(chains=[extract_chain, summarize_chain], verbose=True)

# Execução
document = "A transição para energias renováveis tem mostrado um impacto positivo na redução de emissões, criação de empregos e inovação tecnológica. No entanto, há desafios como a intermitência das fontes renováveis e os custos iniciais elevados."
result = full_chain.run(document)
print(f"✅ Resultado final do Chaining: {result}")
```

## Passo 3: Implementando Routing

O Routing dá ao nosso agente a capacidade de tomar decisões, direcionando o fluxo com base na intenção do utilizador.

```python
# Crie um arquivo chamado: getting_started_routing.py

from langchain_openai import ChatOpenAI
from langchain.schema.runnable import RunnableBranch
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()
llm = ChatOpenAI(temperature=0.1, model_name="gpt-4")

# 1. Classificador de Intenção (O "Cérebro" do Roteador)
classifier_prompt = PromptTemplate(
    input_variables=["user_input"],
    template="""Classifique a intenção do usuário em uma destas categorias: "suporte_tecnico", "informacao", "vendas", "outros".
    Input: {user_input}
    Intenção:"""
)
classifier_chain = LLMChain(llm=llm, prompt=classifier_prompt)

# 2. Handlers Especializados (As "Ações" do Roteador)
support_handler = lambda data: f"🔧 Rota: Suporte Técnico. Ação: Escalar para especialista."
info_handler = lambda data: f"📚 Rota: Informação. Ação: Buscar na base de conhecimento."
sales_handler = lambda data: f"💰 Rota: Vendas. Ação: Conectar com a equipa de vendas."
default_handler = lambda data: f"❓ Rota: Padrão. Ação: Pedir esclarecimento ao utilizador."

# 3. Sistema de Roteamento com RunnableBranch
route_branch = RunnableBranch(
    (lambda x: "suporte_tecnico" in x["intention"].lower(), support_handler),
    (lambda x: "informacao" in x["intention"].lower(), info_handler),
    (lambda x: "vendas" in x["intention"].lower(), sales_handler),
    default_handler
)

# 4. Pipeline Completo de Roteamento
def route_request(user_input: str):
    intention_result = classifier_chain.invoke({"user_input": user_input})
    intention_text = intention_result['text'].strip()
    
    # O RunnableBranch recebe o dicionário e escolhe o caminho
    result = route_branch.invoke({"user_input": user_input, "intention": intention_text})
    return result

# Execução
test_cases = [
    "Meu aplicativo está a crashar quando abro o relatório",
    "Quais são os planos de preços disponíveis?",
    "Gostaria de comprar a versão enterprise",
    "Bom dia, tudo bem?"
]

for case in test_cases:
    routed_action = route_request(case)
    print(f"Input: '{case}'\n➡️  {routed_action}\n")
```

## Conclusão

Parabéns! Você implementou com sucesso um agente básico que utiliza dois dos padrões mais fundamentais. Você está pronto para explorar as outras famílias de capacidades e adicionar mais sofisticação ao seu agente.

**Próximo Passo Recomendado:** Leia o nosso guia de `best_practices.md` para aprender como tornar os seus agentes mais modulares, testáveis e seguros.
