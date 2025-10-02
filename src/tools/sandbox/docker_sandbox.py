"""Simple abstraction around docker for sandboxing tool execution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

try:  # pragma: no cover - optional dependency
    import docker
except Exception:  # pragma: no cover - fallback
    docker = None


@dataclass
class DockerSandbox:
    """Minimal wrapper to run commands inside isolated containers."""

    image: str = "python:3.11-slim"
    network_disabled: bool = True

    def run(self, command: list[str], environment: Dict[str, Any] | None = None, timeout: int = 30) -> str:
        if docker is None:
            raise RuntimeError("Docker SDK não disponível no ambiente atual")

        client = docker.from_env()
        container = client.containers.run(
            self.image,
            command,
            detach=True,
            auto_remove=True,
            environment=environment or {},
            network_disabled=self.network_disabled,
        )
        result = container.wait(timeout=timeout)
        if result.get("StatusCode", 1) != 0:
            logs = container.logs()  # type: ignore[attr-defined]
            raise RuntimeError(f"Sandboxed process falhou: {logs}")
        logs = container.logs()  # type: ignore[attr-defined]
        return logs.decode("utf-8") if isinstance(logs, bytes) else str(logs)
