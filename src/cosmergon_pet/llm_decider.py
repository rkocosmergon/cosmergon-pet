"""LLM-driven decision loop for the Pet.

Architecture (matches Cosmergon Phase 2e + Benchmark Service drehbuch):

    +---------+         /memory/prompt         +-----------+
    |   Pet   | <-----------------------------|  Cosmergon |
    |         |         /state                 |  Backend   |
    |         | ----------------------------->|  v1.60.745 |
    |         |                                +-----------+
    |         |
    |         |   provider.decide(system, memory, world)
    |         | ----+
    |         |     v
    |         |   +-------------+
    |         |   | LLMProvider |  (Ollama today; OpenAI/Claude/...
    |         |   |  adapter    |   later — same protocol)
    |         |   +-------------+
    |         |     |
    |         | <---+ {"action": ..., "params": {...}}
    |         |
    |         |   agent.act(action, **params) ---------> Cosmergon writes
    +---------+                                           self_decision
                                                          (Phase 2e)

The loop is **independent** of the Pet's user-facing button/encoder
flow — both can run concurrently. User presses still execute their
own actions; the LLM ticks alongside.

Failure mode: any provider error skips the tick (logged warning).
The Pet stays alive. On chronic failures (e.g. Ollama down), the Pet
continues to display state from /state polling — only autonomous
decisions pause.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from cosmergon_agent import CosmergonAgent

from .llm import LLMProvider, LLMProviderError

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_S = 60.0
"""Default seconds between LLM decisions. Matches the Cosmergon tick (60 s)."""


VALID_ACTIONS: frozenset[str] = frozenset(
    {
        "place_cells",
        "evolve",
        "create_field",
        "transfer_energy",
        "wait",
    }
)
"""Client-side allowlist of actions the LLM may emit.

Defense-in-depth on top of the backend's per-action validation:
a compromised LLM provider (or prompt injection through the memory
section) cannot trigger arbitrary Cosmergon API endpoints via the Pet.
Anything outside this set is dropped before `agent.act()` is called.

Keep in sync with the SYSTEM_PROMPT below.
"""

# Sensitive params we never log verbatim — UUIDs of other players,
# transfer amounts. The action name + param keys are still logged.
_SENSITIVE_PARAM_KEYS: frozenset[str] = frozenset(
    {
        "to_player_id",
        "amount",
    }
)


SYSTEM_PROMPT = """You are an autonomous agent in Cosmergon — a Conway's Game of Life economy.

Each tick (~60 s) you choose ONE action. Output strict JSON, nothing else:

  {"action": "<name>", "params": {...}}

Valid actions (others will be rejected):
  - place_cells   params: field_id (uuid string), preset (one of:
                  block, blinker, glider, toad)
  - evolve        params: field_id (uuid string)
  - create_field  params: cube_id (uuid string)
  - transfer_energy  params: to_player_id (uuid), amount (number)
  - wait          params: {} — choose this when nothing useful to do

Strategy: keep your fields alive, grow Conway patterns to higher tiers,
accumulate energy. Use prior memory to learn from past outcomes.
"""


async def llm_decision_loop(
    agent: CosmergonAgent,
    provider: LLMProvider,
    *,
    interval_s: float = DEFAULT_INTERVAL_S,
    stop: asyncio.Event | None = None,
    on_decision: callable | None = None,  # type: ignore[type-arg]
) -> None:
    """Background loop: every ``interval_s``, ask provider, execute, repeat.

    Errors are caught and logged; the loop never exits on its own except
    via ``stop`` being set.

    Args:
        agent: SDK agent (must already be opened via ``async with agent``).
        provider: LLM adapter (e.g. :class:`OllamaProvider`).
        interval_s: Seconds between decisions.
        stop: Optional event to terminate the loop cleanly.
        on_decision: Optional callback ``(action, params, elapsed_s, success)``
            called after each decision attempt — useful for the Pet display
            to flash an "LLM acted" indicator.
    """
    stop = stop or asyncio.Event()
    logger.info(
        "llm_decision_loop started provider=%s model=%s interval=%.1fs",
        provider.name,
        provider.model_string,
        interval_s,
    )
    while not stop.is_set():
        try:
            await _one_decision(agent, provider, on_decision)
        except Exception:
            # Catch-all: nothing in this loop is allowed to kill the Pet.
            logger.warning("llm_decision_loop iteration failed", exc_info=True)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_s)
        except asyncio.TimeoutError:
            continue
    logger.info("llm_decision_loop stopped")


async def _one_decision(
    agent: CosmergonAgent,
    provider: LLMProvider,
    on_decision: callable | None,  # type: ignore[type-arg]
) -> None:
    """Single decision round. Logged but does not raise."""
    memory = await _safe_memory(agent)
    world = _format_world(agent.state)

    t0 = time.monotonic()
    try:
        decision = await provider.decide(SYSTEM_PROMPT, memory, world)
    except LLMProviderError as e:
        logger.warning("provider %s failed: %s", provider.name, e)
        if on_decision is not None:
            on_decision("(provider_error)", {}, time.monotonic() - t0, False)
        return

    elapsed = time.monotonic() - t0
    action = decision["action"]
    params = decision["params"]

    # Defense-in-depth: drop actions outside the allowlist before they
    # touch the Cosmergon API. The backend re-validates per-action,
    # so this is a second layer (S157 security panel finding K1).
    if action not in VALID_ACTIONS:
        logger.warning(
            "llm emitted disallowed action %r — dropped (allowed: %s)",
            action,
            sorted(VALID_ACTIONS),
        )
        if on_decision is not None:
            on_decision("(disallowed)", {}, elapsed, False)
        return

    if action == "wait":
        logger.info("llm chose wait (%.1fs)", elapsed)
        if on_decision is not None:
            on_decision("wait", {}, elapsed, True)
        return

    try:
        result = await agent.act(action, **params)
        success = result.success
    except Exception as e:
        logger.warning("agent.act(%s) failed: %s", action, e)
        success = False

    logger.info(
        "llm action=%s params=%s success=%s decided_in=%.1fs",
        action,
        _redact_params(params),
        success,
        elapsed,
    )
    if on_decision is not None:
        on_decision(action, params, elapsed, success)


def _redact_params(params: dict[str, Any]) -> dict[str, Any]:
    """Return params with sensitive values redacted for logging.

    UUIDs of other players + transfer amounts are pseudonymous PII —
    we keep the keys (so the log stays useful for debugging) and
    replace the values with ``<redacted>`` (S157 security panel
    finding E1).
    """
    if not params:
        return params
    return {k: ("<redacted>" if k in _SENSITIVE_PARAM_KEYS else v) for k, v in params.items()}


async def _safe_memory(agent: CosmergonAgent) -> str:
    """Fetch memory prompt; tolerate older backends that lack the endpoint."""
    fetcher = getattr(agent, "fetch_memory_prompt", None)
    if fetcher is None:
        return "(memory endpoint unavailable — SDK or backend too old)"
    try:
        return await fetcher()
    except Exception as e:
        logger.warning("memory fetch failed: %s", e)
        return "(memory fetch failed this tick)"


def _format_world(state: Any) -> str:
    """Compact world-summary for the LLM prompt.

    Kept short: smaller models (3B class) lose the structure when fed
    too much context.
    """
    if state is None:
        return "(no state available — agent not yet connected)"
    fields = list(getattr(state, "fields", []) or [])
    energy = getattr(state, "energy_balance", "?")
    if not fields:
        return f"Energy: {energy}\nFields: (none)"

    visible = fields[:10]
    field_lines = "\n".join(
        f"  - {getattr(f, 'id', '?')}: tier={getattr(f, 'entity_tier', '?')} "
        f"cells={getattr(f, 'active_cell_count', '?')}"
        for f in visible
    )
    extra = f"  ... and {len(fields) - len(visible)} more" if len(fields) > len(visible) else ""
    return f"Energy: {energy}\nFields ({len(fields)}):\n{field_lines}{extra}"
