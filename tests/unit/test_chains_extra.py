"""Tests for ResilientPromptChain — async execute_with_checkpoints."""
from __future__ import annotations

import asyncio

import pytest

from src.chains.resilient_chain import ChainStep, ResilientPromptChain


@pytest.mark.asyncio
async def test_execute_single_sync_step():
    """Single synchronous step executes and returns transformed value."""
    step = ChainStep(name="double", execute=lambda x: x * 2)
    chain = ResilientPromptChain(steps=[step])
    result = await chain.execute_with_checkpoints(5)
    assert result == 10


@pytest.mark.asyncio
async def test_execute_multiple_steps_in_sequence():
    """Steps are executed in order; output of each becomes input of next."""
    steps = [
        ChainStep(name="add10", execute=lambda x: x + 10),
        ChainStep(name="double", execute=lambda x: x * 2),
    ]
    chain = ResilientPromptChain(steps=steps)
    result = await chain.execute_with_checkpoints(5)
    assert result == 30  # (5+10)*2


@pytest.mark.asyncio
async def test_execute_async_step():
    """Step that returns a coroutine is awaited transparently."""

    async def async_add(x: int) -> int:
        await asyncio.sleep(0)
        return x + 100

    step = ChainStep(name="async_add", execute=async_add)
    chain = ResilientPromptChain(steps=[step])
    result = await chain.execute_with_checkpoints(1)
    assert result == 101


@pytest.mark.asyncio
async def test_execute_with_no_steps_returns_input():
    """Empty step list → initial input returned unchanged."""
    chain = ResilientPromptChain(steps=[])
    result = await chain.execute_with_checkpoints("hello")
    assert result == "hello"


@pytest.mark.asyncio
async def test_execute_step_receives_previous_output():
    """Each step receives the output of the previous step."""
    received: list[int] = []

    def capture(x: int) -> int:
        received.append(x)
        return x + 1

    steps = [ChainStep(name=f"s{i}", execute=capture) for i in range(3)]
    chain = ResilientPromptChain(steps=steps)
    result = await chain.execute_with_checkpoints(10)
    assert result == 13
    assert received == [10, 11, 12]
