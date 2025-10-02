"""Implementa estratégia simples de esquecimento inteligente."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class MemoryStore:
    data: Dict[str, Dict]

    def get_all_memories(self) -> Dict[str, Dict]:
        return self.data

    def mark_for_removal(self, key: str) -> None:
        self.data.pop(key, None)

    def replace(self, key: str, value: Dict) -> None:
        self.data[key] = value

    def execute_cleanup(self) -> int:
        return 0


@dataclass
class IntelligentForgetting:
    memory: MemoryStore

    def adaptive_forget(self) -> int:
        removed = 0
        for key, value in list(self.memory.get_all_memories().items()):
            if value.get("relevance", 1.0) < 0.1:
                self.memory.mark_for_removal(key)
                removed += 1
        removed += self.memory.execute_cleanup()
        return removed
