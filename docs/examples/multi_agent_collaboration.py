"""
Multi-Agent Collaboration: Múltiplos agentes especializados colaborando
Caso de uso: Sistema de pesquisa e análise de mercado
"""
from langchain.agents import AgentType, initialize_agent
from langchain.tools import Tool
from langchain_community.llms import OpenAI

llm = OpenAI(temperature=0.1)

# Ferramentas Especializadas
research_tool = Tool(
    name="Researcher",
    func=lambda x: f"Pesquisando sobre: {x}",
    description="Pesquisa e compila dados sobre um tópico específico."
)

analysis_tool = Tool(
    name="Analyst",
    func=lambda x: f"Analisando dados: {x}",
    description="Analisa os dados compilados e identifica tendências."
)

writing_tool = Tool(
    name="Writer",
    func=lambda x: f"Escrevendo relatório: {x}",
    description="Transforma a análise em um relatório claro e conciso."
)

# Inicializando o Agente com Capacidade de Usar Ferramentas
agent = initialize_agent(
    tools=[research_tool, analysis_tool, writing_tool],
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)

# Execução
queries = [
    "Quais são as tendências emergentes em IA generativa para 2024?",
]

for query in queries:
    print(f"\n🔍 Query: {query}")
    result = agent.run(query)
    print(f"✅ Resposta: {result}")
