"""
Colaboração & Integração: Sistema de Pesquisa com Agente Supervisor
Caso de uso: Sistema de pesquisa com múltiplos agentes especializados
"""
from google.adk.agents import Agent
from google.adk.tools import code_executor, google_search


# Configuração dos agentes especializados
research_agent = Agent(
    name="ResearchAgent",
    model="gemini-2.0-flash-exp",
    instruction="Pesquise informações detalhadas sobre o tópico fornecido.",
    tools=[google_search],
)

writer_agent = Agent(
    name="WriterAgent",
    model="gemini-2.0-flash-exp",
    instruction="Escreva um artigo baseado no resumo de pesquisa fornecido.",
    tools=[code_executor],
)

# Agente supervisor para orquestração
supervisor_agent = Agent(
    name="SupervisorAgent",
    model="gemini-2.0-flash-exp",
    instruction="Orquestre a pesquisa e a escrita de artigos.",
    tools=[research_agent, writer_agent],
)


# Simular uma tarefa de pesquisa e escrita
async def run_research_and_write(task: str) -> None:
    research_summary = await research_agent.arun(task)
    article = await writer_agent.arun(research_summary)
    print(f"Artigo Final: {article}")


async def main() -> None:
    await run_research_and_write("Tendências emergentes em IA para 2025")


if __name__ == "__main__":
    import asyncio

    import nest_asyncio

    nest_asyncio.apply()
    asyncio.run(main())
