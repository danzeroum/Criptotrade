"""
Prompt Chaining: Execução sequencial onde a saída de uma etapa alimenta a próxima
Caso de uso: Pipeline de processamento de documentos
"""
from langchain.chains import LLMChain, SimpleSequentialChain
from langchain.prompts import PromptTemplate
from langchain_community.llms import OpenAI

# Configuração do LLM
llm = OpenAI(temperature=0.1)

# Chain 1: Extrair informações chave
extract_prompt = PromptTemplate(
    input_variables=["document"],
    template="Extraia as 3 informações principais deste documento: {document}"
)
extract_chain = LLMChain(llm=llm, prompt=extract_prompt, output_key="key_points")

# Chain 2: Gerar resumo baseado nas informações extraídas
summarize_prompt = PromptTemplate(
    input_variables=["key_points"],
    template="Com base nestes pontos principais: {key_points}, gere um resumo conciso."
)
summarize_chain = LLMChain(llm=llm, prompt=summarize_prompt, output_key="summary")

# Chain 3: Validar qualidade do resumo
validate_prompt = PromptTemplate(
    input_variables=["summary"],
    template="Avalie a qualidade deste resumo (1-10): {summary}. Justifique brevemente."
)
validate_chain = LLMChain(llm=llm, prompt=validate_prompt, output_key="validation")

# Encadeamento completo
full_chain = SimpleSequentialChain(
    chains=[extract_chain, summarize_chain, validate_chain],
    verbose=True
)

# Execução
document = "A transição para energias renováveis tem mostrado um impacto positivo na redução de emissões, criação de empregos e inovação tecnológica. No entanto, há desafios como a intermitência das fontes renováveis e os custos iniciais elevados."

result = full_chain.run(document)
print(f"Resultado final: {result}")
