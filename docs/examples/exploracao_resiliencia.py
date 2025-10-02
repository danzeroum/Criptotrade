"""
Exploração & Resiliência: Agente de Cibersegurança
Caso de uso: Exploração de rede e gestão de anomalias
"""
from google.adk.agents import Agent
from google.adk.tools import anomaly_detector, network_scanner


# Configuração dos agentes especializados
exploration_agent = Agent(
    name="ExplorationAgent",
    model="gemini-2.0-flash-exp",
    instruction="Explore a rede em busca de vulnerabilidades.",
    tools=[network_scanner],
)

recovery_agent = Agent(
    name="RecoveryAgent",
    model="gemini-2.0-flash-exp",
    instruction="Gerencie e recupere de falhas detectadas.",
    tools=[anomaly_detector],
)

# Orquestração com agente supervisor
supervisor_agent = Agent(
    name="SupervisorAgent",
    model="gemini-2.0-flash-exp",
    instruction="Supervisione a exploração de rede e recuperação de falhas.",
    tools=[exploration_agent, recovery_agent],
)


# Simular uma tarefa de cibersegurança
async def run_cybersecurity_task() -> None:
    network_results = await exploration_agent.arun("Scanear rede para vulnerabilidades.")
    if "anomalia" in network_results.lower():
        recovery_results = await recovery_agent.arun(network_results)
        print(f"Resultados de Recuperação: {recovery_results}")
    else:
        print(f"Resultados de Exploração: {network_results}")


async def main() -> None:
    await run_cybersecurity_task()


if __name__ == "__main__":
    import asyncio

    import nest_asyncio

    nest_asyncio.apply()
    asyncio.run(main())
