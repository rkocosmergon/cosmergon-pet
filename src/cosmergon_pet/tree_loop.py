"""Rule-based decision loop — drop-in alternative to ``llm_decision_loop``.

Why a separate loop? The LLM decider speaks an HTTP-provider protocol
(``provider.decide(system, memory, world, schema=...)``), while the tree
decider operates on the ``GameState`` directly via
``TreeDecider().decide(state)``. Rather than reshape one to match the
other, we keep two thin loops with the same lifecycle (``stop``-event,
``on_decision``-callback, exception-swallowing).

Use it from ``face.py`` analogous to the LLM path::

    if decider == "tree":
        from .decider_tree import TreeDecider
        from .tree_loop import tree_decision_loop
        tree_task = asyncio.create_task(
            tree_decision_loop(agent, TreeDecider(), interval_s=..., stop=stop)
        )

The loop matches the ollama-path's defensive contract: every error is
caught and logged; the loop never raises. On chronic SDK failures, the
Pet keeps polling state — only autonomous decisions pause.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from cosmergon_agent import CosmergonAgent

from .decider_tree import VALID_ACTIONS, TreeDecider

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_S = 60.0


def _redact_params(params: dict[str, Any]) -> dict[str, Any]:
    """Same hygiene as `llm_decider._redact_params` — never log UUIDs/amounts verbatim."""
    sensitive = {"to_player_id", "amount", "field_id", "cube_id", "listing_id"}
    return {k: ("<redacted>" if k in sensitive else v) for k, v in params.items()}


async def _one_tree_decision(
    agent: CosmergonAgent,
    decider: TreeDecider,
    on_decision: Any | None,
) -> None:
    """Single decision round — never raises."""
    state = getattr(agent, "state", None)
    if state is None:
        # _poll_state mirrors agent._state from /state polling. If still
        # None, the SDK has not yet seen a state — skip this tick.
        logger.debug("tree_decision: agent.state still None, skip")
        return

    t0 = time.monotonic()
    try:
        action, params = await decider.decide(state)
    except Exception as e:
        logger.warning("tree decider failed: %s", e)
        if on_decision is not None:
            on_decision("(tree_error)", {}, time.monotonic() - t0, False)
        return

    elapsed = time.monotonic() - t0

    # Defense-in-depth: same allowlist guard as LLM path. The tree's own
    # action_fns produce only allowlisted actions, but a future regression
    # is cheap to catch here.
    if action not in VALID_ACTIONS:
        logger.warning(
            "tree emitted disallowed action %r — dropped (allowed: %s)",
            action,
            sorted(VALID_ACTIONS),
        )
        if on_decision is not None:
            on_decision("(disallowed)", {}, elapsed, False)
        return

    if action == "wait":
        logger.info("tree chose wait (%.3fs)", elapsed)
        if on_decision is not None:
            on_decision("wait", {}, elapsed, True)
        return

    try:
        result = await agent.act(action, **params)
        success = bool(getattr(result, "success", False))
    except Exception as e:
        logger.warning("agent.act(%s) failed: %s", action, e)
        success = False

    logger.info(
        "tree action=%s params=%s success=%s decided_in=%.3fs",
        action,
        _redact_params(params),
        success,
        elapsed,
    )
    if on_decision is not None:
        on_decision(action, params, elapsed, success)


async def tree_decision_loop(
    agent: CosmergonAgent,
    decider: TreeDecider,
    *,
    interval_s: float = DEFAULT_INTERVAL_S,
    stop: asyncio.Event | None = None,
    on_decision: Any | None = None,
) -> None:
    """Background loop: every ``interval_s``, ask the tree decider, execute, repeat.

    Mirrors the lifecycle contract of ``llm_decision_loop``: errors caught and
    logged; the loop never exits on its own except via ``stop`` being set.

    Args:
        agent: SDK agent, must already be opened via ``async with agent``.
        decider: ``TreeDecider`` instance (or any class with the same
            ``decide(state) -> (action, params)`` signature).
        interval_s: Seconds between decisions. Tree-Inferenz selbst ist
            mikrosekunden-schnell; das Intervall begrenzt die Backend-
            Action-Rate analog zum LLM-Pfad.
        stop: Optional event to terminate the loop cleanly.
        on_decision: Optional callback ``(action, params, elapsed_s, success)``
            — used by the Pet display to flash a "decider acted" indicator.
    """
    stop = stop or asyncio.Event()
    logger.info(
        "tree_decision_loop started decider=%s interval=%.1fs",
        getattr(decider, "name", "tree"),
        interval_s,
    )
    while not stop.is_set():
        try:
            await _one_tree_decision(agent, decider, on_decision)
        except Exception:
            # Catch-all: nothing in this loop is allowed to kill the Pet.
            logger.warning("tree_decision_loop iteration failed", exc_info=True)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_s)
        except asyncio.TimeoutError:
            continue
    logger.info("tree_decision_loop stopped")
