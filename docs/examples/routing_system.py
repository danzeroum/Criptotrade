"""
Routing System: Sistema de decisão que direciona para diferentes fluxos
Caso de uso: Sistema de atendimento ao cliente
"""
from langchain.schema.runnable import RunnableBranch
from langchain_community.llms import OpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

llm = OpenAI(temperature=0.1)

# Classificador de Intenção
classifier_prompt = PromptTemplate(
    input_variables=["user_input"],
    template="""
    Classifique a intenção do usuário:
    - "suporte_tecnico": problemas técnicos, erro no sistema
    - "informacao": perguntas sobre produtos, preços, funcionalidades  
    - "vendas": interesse em comprar, orçamento
    - "outros": não se encaixa nas categorias acima
    
    Input: {user_input}
    Intenção:
    """
)
classifier_chain = LLMChain(llm=llm, prompt=classifier_prompt, output_key="intention")

# Handlers Especializados
support_handler = lambda x: f"Encaminhando para suporte técnico: {x}"
info_handler = lambda x: f"Fornecendo informações detalhadas: {x}"
sales_handler = lambda x: f"Conectando com equipe de vendas: {x}"
default_handler = lambda x: f"Direcionando para atendente humano: {x}"

# Sistema de Roteamento com RunnableBranch
route_branch = RunnableBranch(
    (lambda x: "suporte_tecnico" in x["intention"].lower(), support_handler),
    (lambda x: "informacao" in x["intention"].lower(), info_handler),
    (lambda x: "vendas" in x["intention"].lower(), sales_handler),
    default_handler
)

# Pipeline Completo
def route_request(user_input):
    intention_result = classifier_chain.run(user_input=user_input)
    result = route_branch.invoke({"user_input": user_input, "intention": intention_result})
    return {
        "original_input": user_input,
        "detected_intention": intention_result,
        "routed_action": result,
        "timestamp": "2024-01-01T00:00:00Z"
    }

# Teste
test_cases = [
    "Meu aplicativo está crashando quando abro o relatório",
    "Quais são os planos de preços disponíveis?",
    "Gostaria de comprar a versão enterprise",
    "Bom dia, tudo bem?"
]

for case in test_cases:
    result = route_request(case)
    print(f"Input: {case}")
    print(f"Resultado: {result}\n")
