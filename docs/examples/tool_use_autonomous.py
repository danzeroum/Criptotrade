"""
Tool Use: Agente decide autonomamente quando e quais ferramentas usar
Caso de uso: Assistente inteligente com acesso a APIs externas
"""
import ast
import operator
import re
from langchain.agents import AgentType, initialize_agent
from langchain.tools import Tool
from langchain_community.llms import OpenAI

llm = OpenAI(temperature=0.1)

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_calculator(expression: str):
    """Avalia uma expressão aritmética simples sem usar eval() (evita RCE)."""

    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
            return _ALLOWED_OPERATORS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
            return _ALLOWED_OPERATORS[type(node.op)](_eval(node.operand))
        raise ValueError("Expressão não suportada")

    return _eval(ast.parse(expression, mode="eval").body)


def unit_converter(query: str):
    patterns = {
        "km to miles": lambda value: value * 0.621371,
        "celsius to fahrenheit": lambda value: (value * 9 / 5) + 32,
    }
    selected = next((name for name in patterns if name in query.lower()), None)
    numbers = re.findall(r"\d+\.?\d*", query)
    if not selected or not numbers:
        return "Conversão não suportada"
    value = float(numbers[0])
    return patterns[selected](value)


# Ferramentas Disponíveis
tools = [
    Tool(
        name="Calculator",
        func=safe_calculator,  # Avaliador seguro (sem eval)
        description="Útil para cálculos matemáticos",
    ),
    Tool(
        name="InformationFinder",
        func=lambda x: f"Informações sobre: {x}",
        description="Útil para encontrar informações gerais",
    ),
    Tool(
        name="UnitConverter",
        func=unit_converter,
        description="Útil para converter unidades como km para milhas, Celsius para Fahrenheit",
    ),
]

# Inicializando o Agente com Capacidade de Usar Ferramentas
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
)

# Testes Onde o Agente Decide Qual Ferramenta Usar
queries = [
    "Quanto é 15 * 24?",
    "Converta 100 km para milhas",
    "Me conte sobre inteligência artificial",
    "Qual é a temperatura de 25°C em Fahrenheit?",
]

for query in queries:
    print(f"\n🔍 Query: {query}")
    result = agent.run(query)
    print(f"✅ Resposta: {result}")
