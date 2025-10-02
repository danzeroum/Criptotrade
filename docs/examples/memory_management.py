"""
Memory Management: Ciclo completo de armazenamento e recuperação
Caso de uso: Assistente personalizado que lembra preferências
"""
from langchain.memory import ConversationBufferMemory
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_community.llms import OpenAI

# Configuração com Memória Persistente
memory = ConversationBufferMemory(return_messages=True)
llm = OpenAI(temperature=0.1)

# Chain Conversacional com Memória
conversation_chain = LLMChain(
    llm=llm,
    memory=memory,
    verbose=True,
    prompt=PromptTemplate(
        input_variables=["input"],
        template="Você é um assistente que lembra preferências. {input}"
    )
)

# Simulação de Múltiplas Sessões com Persistência
def simulate_conversation_session(messages):
    responses = []
    for message in messages:
        response = conversation_chain.predict(input=message)
        responses.append({
            "user_message": message,
            "assistant_response": response,
            "session_context": conversation_chain.memory.load_memory_variables({})
        })
    return responses

# Sessão 1: Estabelecendo Preferências
print("=== SESSÃO 1: Estabelecendo Preferências ===")
session1_messages = [
    "Meu nome é João Silva",
    "Eu gosto de café preto sem açúcar",
    "Minha empresa é a TechSolutions Ltda"
]

session1_results = simulate_conversation_session(session1_messages)

# Sessão 2: Recuperando Informações da Memória
print("\n=== SESSÃO 2: Recuperando da Memória ===")
session2_messages = [
    "Você se lembra do meu nome?",
    "Como eu gosto do meu café?",
    "Qual é o nome da minha empresa?"
]

session2_results = simulate_conversation_session(session2_messages)

# Demonstração do Conteúdo da Memória
print("\n=== CONTEÚDO DA MEMÓRIA ===")
print(conversation_chain.memory.load_memory_variables({}))
