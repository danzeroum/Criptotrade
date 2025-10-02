"""Testes para validar componentes de execução."""
from pathlib import Path


def test_execucao_adr_existe() -> None:
    assert Path("docs/ADRs/ADR-005-Execucao.md").exists()


def test_exemplo_execucao_contem_prompt_chaining() -> None:
    content = Path("docs/examples/execucao_tarefas.py").read_text(encoding="utf-8")
    assert "LLMChain" in content
    assert "PromptTemplate" in content
