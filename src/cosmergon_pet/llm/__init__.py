"""Pluggable LLM providers for the Pet.

The Pet itself stays provider-agnostic: it asks Cosmergon for a memory
prompt + world state, hands them to a provider, gets back an action.

This package follows the Cosmergon Benchmark Service convention
(model strings of form ``<provider>/<name>``) so a Pet running with
``ollama/llama3.2:3b`` and a Pet running with ``openai/gpt-4o`` will,
once the Benchmark Service is live, appear on the same leaderboard
without any Pet-side change.

Today only :class:`OllamaProvider` is implemented. Other providers
(OpenAI, Anthropic, OpenRouter, etc.) drop into the registry below
with one file each.
"""

from __future__ import annotations

from .base import LLMProvider, LLMProviderError
from .ollama import OllamaProvider

_REGISTRY: dict[str, type[LLMProvider]] = {
    "ollama": OllamaProvider,
}


def build_provider(name: str, **config: object) -> LLMProvider:
    """Build a provider instance by name.

    Args:
        name: registry key, e.g. ``"ollama"``.
        **config: provider-specific kwargs (forwarded to ``__init__``).

    Raises:
        ValueError: unknown provider name.
    """
    cls = _REGISTRY.get(name)
    if cls is None:
        known = ", ".join(sorted(_REGISTRY))
        raise ValueError(f"unknown llm provider {name!r}; available: {known}")
    return cls(**config)  # type: ignore[arg-type]


def available_providers() -> list[str]:
    """Names of providers that can be used with :func:`build_provider`."""
    return sorted(_REGISTRY)


__all__ = [
    "LLMProvider",
    "LLMProviderError",
    "OllamaProvider",
    "available_providers",
    "build_provider",
]
