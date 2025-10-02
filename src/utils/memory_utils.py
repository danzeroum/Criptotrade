"""Utilitários para gestão de memória de agentes."""
from __future__ import annotations

from typing import Any


class MemoryStore:
    """Armazena preferências persistentes em memória."""

    def __init__(self) -> None:
        self._storage: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._storage[key] = value

    def get(self, key: str, default: Any | None = None) -> Any | None:
        return self._storage.get(key, default)

    def snapshot(self) -> dict[str, Any]:
        """Retorna uma cópia da memória atual."""

        return dict(self._storage)
