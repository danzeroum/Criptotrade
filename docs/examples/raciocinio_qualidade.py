"""
Raciocínio & Qualidade: Geração e autoavaliação de código
Caso de uso: Geração de Função para Cálculo de Fatorial
"""
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI


# Configuração do LLM
llm = ChatOpenAI(model_name="gpt-4", temperature=0.2)

# Definir o prompt para geração de código
generate_code_prompt = PromptTemplate(
    input_variables=["task"],
    template="Gere um código Python para {task}.",
)
generate_code_chain = LLMChain(llm=llm, prompt=generate_code_prompt)

# Definir o prompt para autoavaliação do código
evaluate_code_prompt = PromptTemplate(
    input_variables=["code"],
    template="Avalie a qualidade do código gerado: {code}. Identifique erros ou melhorias.",
)
evaluate_code_chain = LLMChain(llm=llm, prompt=evaluate_code_prompt)


# Orquestração completa
async def run_code_generation_and_evaluation(task: str) -> None:
    generated_code = await generate_code_chain.arun(task)
    evaluation = await evaluate_code_chain.arun(generated_code)
    print(f"Código Gerado: {generated_code}")
    print(f"Avaliação: {evaluation}")


async def main() -> None:
    await run_code_generation_and_evaluation("Calcular o fatorial de um número")


if __name__ == "__main__":
    import asyncio

    import nest_asyncio

    nest_asyncio.apply()
    asyncio.run(main())
