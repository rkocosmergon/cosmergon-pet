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
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Ask the LLM for the next action.

        Args:
            system_prompt: Role + action vocabulary + output schema.
            memory: Cosmergon-rendered memory section
                (from ``agent.fetch_memory_prompt()``).
            world: Compact world-state summary
                (energy, fields, neighbours).
            schema: Optional JSON-Schema constraining the response.
                When supplied, providers that support structured output
                (Ollama since Q1/2025, OpenAI tool-use, Anthropic) MUST
                pass it to the model so the response is forced to match.
                When None, providers fall back to "any valid JSON".

        Returns:
            Dict with at least ``action`` (str) and ``params`` (dict).
            ``action="wait"`` is a valid no-op decision.

        Raises:
            LLMProviderError: any failure that should skip this tick.
        """
        ...  # pragma: no cover

    async def reflect(
        self,
        signals: dict[str, Any],
        persona: str,
        agent_name: str,
    ) -> dict[str, str] | None:
        """Synthesize a self-reflection from collected decision signals.

        Companion to ``decide``. Called by ``llm_decision_loop`` whenever
        ``state.reflection_due`` is set — the LLM looks at its top-5 best
        and bottom-5 worst recent decisions plus its dominant action
        patterns and produces three structured strings (lessons / avoid /
        double_down). The Pet then posts them back via
        ``agent.post_reflection()``.

        See ``konzept-api-agent-reflection.md`` for the wider mechanism.

        Args:
            signals: payload from ``agent.fetch_reflection_signals()`` —
                contains ``top_5``, ``bottom_5``, ``dominant_actions``,
                ``decisions_in_window``, ``since_tick``, ``horizon``.
            persona: ``state.persona_type`` — drives the system-prompt
                tone for the reflection (warrior reflects different from
                farmer).
            agent_name: ``state.agent_name`` — addresses the agent in
                first person ("As Comet-hand, you ...").

        Returns:
            Dict with keys ``lessons`` (100-500 chars), ``avoid``
            (50-200 chars), ``double_down`` (50-200 chars), or ``None``
            if the LLM call failed or the response did not validate
            against the schema. Pet treats ``None`` as "skip this
            reflection round, try again next time it's due".

        Raises:
            LLMProviderError: only on hard failures the Pet wants to log
                (network down, repeated 5xx). Validation errors return
                ``None`` instead of raising — they are not exceptional.

        Default implementation returns ``None`` (no-op) so existing
        adapters that haven't implemented reflection still satisfy the
        Protocol. Override in concrete providers (OllamaProvider, etc.).
        """
        return None  # pragma: no cover
