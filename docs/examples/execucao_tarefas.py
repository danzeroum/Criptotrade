"""
Execução de Tarefas: Orquestração de tarefas complexas
Caso de uso: Processamento de Notas Fiscais (NFe)
"""
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI


# Configuração do LLM
llm = ChatOpenAI(model_name="gpt-4", temperature=0.2)

# Definir o prompt para cada etapa
extract_prompt = PromptTemplate(
    input_variables=["document"],
    template="Extraia os dados relevantes da NFe: {document}",
)
extract_chain = LLMChain(llm=llm, prompt=extract_prompt, output_key="extracted_data")

validate_prompt = PromptTemplate(
    input_variables=["data"],
    template="Valide os dados extraídos: {data}",
)
validate_chain = LLMChain(llm=llm, prompt=validate_prompt, output_key="validation_result")

# Orquestração completa
full_chain = LLMChain(
    llm=llm,
    prompt=PromptTemplate(template="{extracted_data}\n{validation_result}"),
    memory=ConversationBufferMemory(),
    verbose=True,
)


# Simular uma tarefa de processamento de NFe
async def run_nfe_processing(document: str) -> None:
    extracted = await extract_chain.arun(document)
    validated = await validate_chain.arun(extracted)
    print(f"Dados Validados: {validated}")


async def main() -> None:
    document = "NFe emitida por TechSolutions Ltda, valor: R$1000,00, data: 2024-01-01"
    await run_nfe_processing(document)


if __name__ == "__main__":
    import asyncio

    import nest_asyncio

    nest_asyncio.apply()
    asyncio.run(main())
