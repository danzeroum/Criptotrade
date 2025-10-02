"""Testes para validar componentes de resiliência."""
from pathlib import Path


def test_resiliencia_adr_existe() -> None:
    assert Path("docs/ADRs/ADR-009-Resiliencia.md").exists()


def test_exemplo_resiliencia_tem_recovery() -> None:
    content = Path("docs/examples/exploracao_resiliencia.py").read_text(encoding="utf-8")
    assert "RecoveryAgent" in content
    assert "anomalia" in content.lower()
