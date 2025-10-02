"""Parallel execution helper that respects resource limits."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Iterable, List

TaskLike = Awaitable[Any] | Callable[[], Awaitable[Any]]


@dataclass
class ParallelResourceManager:
    """Execute asynchronous tasks while observing basic limits."""

    limits: Dict[str, float] = field(
        default_factory=lambda: {
            "max_concurrent": 5,
        }
    )

    async def execute_parallel_with_limits(self, tasks: Iterable[TaskLike]) -> List[Any]:
        semaphore = asyncio.Semaphore(int(self.limits.get("max_concurrent", 5)))

        async def _ensure(task: TaskLike) -> Any:
            if callable(task):
                return await task()
            return await task

        async def _run(task: TaskLike) -> Any:
            async with semaphore:
                return await _ensure(task)

        return await asyncio.gather(*[_run(task) for task in tasks])
