"""Optional LLM client for agentic reasoning (Chain-of-Thought / Reflection).

This module turns the "AI" in *AI trading platform* into something real: when
enabled, the StrategyAgent and RiskAgent consult a large language model to reason
over the deterministic technical-analysis context. It is **disabled by default**.

Design guarantees (do not break these):

* **Off by default.** The trading cycle stays fully deterministic unless
  ``LLM_ENABLED=true`` *and* a provider API key is configured. This preserves the
  ``EXCHANGE_DRY_RUN`` zero-network guarantee and the offline test suite.
* **Best-effort.** Every call is wrapped: any error (missing dep, network,
  bad output) returns ``None`` and callers fall back to deterministic logic. The
  LLM is *advisory* — guardrails and HITL remain the safety net.
* **Lazy imports.** Provider SDKs are imported inside methods so this module
  imports cleanly even where ``langchain`` is not installed (e.g. the lean CI).

Provider is pluggable via ``LLM_PROVIDER``:

* ``google`` (default) — Gemini via ``langchain-google-genai`` (pinned dep).
* ``openai``  — via ``langchain-openai`` (optional).
* ``anthropic`` — Claude via ``langchain-anthropic`` (optional).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

_DEFAULT_MODELS = {
    "google": "gemini-1.5-flash",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
}


def _truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _provider() -> str:
    return (os.getenv("LLM_PROVIDER", "google") or "google").strip().lower()


def _api_key_for(provider: str) -> Optional[str]:
    keys = {
        "google": os.getenv("GOOGLE_API_KEY"),
        "openai": os.getenv("OPENAI_API_KEY"),
        "anthropic": os.getenv("ANTHROPIC_API_KEY"),
    }
    return keys.get(provider)


def is_llm_enabled() -> bool:
    """True only when explicitly enabled AND a key for the provider is present."""
    if not _truthy(os.getenv("LLM_ENABLED")):
        return False
    return bool(_api_key_for(_provider()))


class LLMClient:
    """Thin, fail-safe wrapper over a chat LLM (lazy provider construction)."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
    ) -> None:
        self.provider = (provider or _provider()).strip().lower()
        self.model = model or os.getenv("LLM_MODEL") or _DEFAULT_MODELS.get(
            self.provider, _DEFAULT_MODELS["google"]
        )
        self.temperature = temperature
        self._chat: Any = None  # built lazily on first use

    # ------------------------------------------------------------------ internals
    def _build_chat(self) -> Any:
        """Construct the provider chat model. Raises if the SDK is unavailable."""
        api_key = _api_key_for(self.provider)
        if not api_key:
            raise RuntimeError(f"No API key configured for provider '{self.provider}'")

        if self.provider == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(
                model=self.model, google_api_key=api_key, temperature=self.temperature
            )
        if self.provider == "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(model=self.model, api_key=api_key, temperature=self.temperature)
        if self.provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(model=self.model, api_key=api_key, temperature=self.temperature)
        raise RuntimeError(f"Unknown LLM provider '{self.provider}'")

    def _complete_sync(self, system: str, user: str) -> Optional[str]:
        """Blocking completion. Returns text or None on any failure."""
        try:
            if self._chat is None:
                self._chat = self._build_chat()
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [SystemMessage(content=system), HumanMessage(content=user)]
            response = self._chat.invoke(messages)
            text = getattr(response, "content", None)
            if isinstance(text, list):  # some providers return content parts
                text = " ".join(str(p) for p in text)
            return str(text).strip() if text else None
        except Exception as exc:  # noqa: BLE001 - advisory layer must never raise
            logger.warning("LLM completion failed (%s/%s): %s", self.provider, self.model, exc)
            return None

    # -------------------------------------------------------------------- public
    async def reason(self, system: str, user: str) -> Optional[str]:
        """Async completion (runs the blocking SDK call in a worker thread).

        Bounded by ``LLM_TIMEOUT_SECONDS`` (default 30) so a hung provider call
        can never stall a trading cycle — on timeout the advisory layer simply
        yields ``None`` and callers fall back to deterministic logic.
        """
        try:
            timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
        except ValueError:
            timeout = 30.0
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._complete_sync, system, user), timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(
                "LLM completion timed out after %.0fs (%s/%s)", timeout, self.provider, self.model
            )
            return None

    async def reason_json(self, system: str, user: str) -> Optional[dict[str, Any]]:
        """Completion expected to return JSON. Returns parsed dict or None."""
        raw = await self.reason(system, user)
        if not raw:
            return None
        return _extract_json(raw)


def _extract_json(text: str) -> Optional[dict[str, Any]]:
    """Best-effort JSON extraction from an LLM response (handles ```json fences)."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None


# Process-wide singleton (cheap; chat model is built lazily inside the client).
_CLIENT: Optional[LLMClient] = None


def get_llm_client() -> Optional[LLMClient]:
    """Return a shared LLMClient when enabled, else None (deterministic mode)."""
    global _CLIENT
    if not is_llm_enabled():
        return None
    if _CLIENT is None:
        _CLIENT = LLMClient()
    return _CLIENT


def reset_llm_client() -> None:
    """Drop the cached client (used by tests after toggling env)."""
    global _CLIENT
    _CLIENT = None


__all__ = [
    "LLMClient",
    "is_llm_enabled",
    "get_llm_client",
    "reset_llm_client",
]
