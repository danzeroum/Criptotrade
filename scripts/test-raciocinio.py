"""Testes para validar componentes de raciocínio."""
from pathlib import Path


def test_raciocinio_adr_existe() -> None:
    assert Path("docs/ADRs/ADR-006-Raciocinio.md").exists()


def test_exemplo_raciocinio_menciona_autoavaliacao() -> None:
    content = Path("docs/examples/raciocinio_qualidade.py").read_text(encoding="utf-8")
    assert "Avalie a qualidade" in content
