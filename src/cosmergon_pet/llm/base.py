"""LLM provider protocol — what every adapter must offer.

Designed so that a future Cosmergon Benchmark Service run reads the same
shape: ``model_string`` is the provider-prefixed identifier that ends up
in ``benchmark_runs.metadata.model``.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class LLMProviderError(Exception):
    """Provider failure (network, malformed response, timeout).

    The Pet decision loop catches this and skips the tick — the Pet
    stays alive, no crash, no user-visible disruption beyond a missed
    decision.
    """


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal contract for LLM adapters used by the Pet.

    Implementations should be **stateless** (no mutable session state
    between calls). They may keep an HTTP client open across calls for
    connection reuse — that is an internal optimisation, not part of
    the contract.

    Attributes:
        name: Short registry name (e.g. ``"ollama"``).
        model_string: Benchmark-Service-compatible identifier. Format:
            ``<provider>/<model>`` (e.g. ``"ollama/llama3.2:3b"``).
            Used as run metadata so Pet runs are comparable on the
            future Cosmergon leaderboard.
    """

    name: str
    model_string: str

    async def decide(
        self,
        system_prompt: str,
        memory: str,
        world: str,
    ) -> dict[str, Any]:
        """Ask the LLM for the next action.

        Args:
            system_prompt: Role + action vocabulary + output schema.
            memory: Cosmergon-rendered memory section
                (from ``agent.fetch_memory_prompt()``).
            world: Compact world-state summary
                (energy, fields, neighbours).

        Returns:
            Dict with at least ``action`` (str) and ``params`` (dict).
            ``action="wait"`` is a valid no-op decision.

        Raises:
            LLMProviderError: any failure that should skip this tick.
        """
        ...  # pragma: no cover
