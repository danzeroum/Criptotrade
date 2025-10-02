"""
Memória & Aprendizagem: Assistente Pessoal com Preferências
Caso de uso: Assistente que armazena preferências do usuário
"""
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI


# Configuração do LLM e Memória
llm = ChatOpenAI(model_name="gpt-4", temperature=0.2)
memory = ConversationBufferMemory()

# Definir o prompt para armazenar e utilizar preferências
personal_assistant_prompt = PromptTemplate(
    input_variables=["input"],
    template="""
    Você é um assistente pessoal que armazena preferências.
    Entrada: {input}
    Resposta: Utilize as preferências armazenadas para responder.
    """,
)

# Criar a cadeia de LLM para assistente pessoal
personal_assistant_chain = LLMChain(llm=llm, prompt=personal_assistant_prompt, memory=memory)


# Simular uma tarefa de assistente pessoal
async def run_personal_assistant(user_input: str) -> None:
    response = await personal_assistant_chain.arun(user_input)
    print(f"Resposta do Assistente: {response}")


async def main() -> None:
    await run_personal_assistant("Meu nome é João e eu prefiro voos noturnos.")
    await run_personal_assistant("Encontre um voo para mim para Paris.")


if __name__ == "__main__":
    import asyncio

    import nest_asyncio

    nest_asyncio.apply()
    asyncio.run(main())
