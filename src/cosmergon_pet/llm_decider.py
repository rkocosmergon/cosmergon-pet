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
import json
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
Every ~60 seconds you must take a turn. You decide what to do.

How to answer:
  1. Output a single JSON object — no prose, no markdown fences, no comments.
  2. Pick exactly ONE numbered line from the "Available actions" list.
  3. Copy the JSON snippet shown after the arrow on that line VERBATIM
     (every UUID character). Never invent or shorten any value.

Strategy:
  - Energy decays every tick. Doing nothing means losing energy slowly
    until you die. Wait is rarely the right choice for a healthy agent.
  - Conway patterns generate energy proportional to their live-cell count.
    Adding cells (place_cells) is the cheapest way to grow income.
  - When a field is mature, evolve it to the next tier — each tier roughly
    doubles output. Required entity_type changes per tier (oscillator → T2,
    spaceship → T3, gun → T4, breeder → T5).
  - Choose wait only when the listed actions truly cannot help: every
    place_cells is unaffordable AND no field is evolve-eligible.

Decision examples:
  Healthy state, energy high, field has 3 cells:
    → place_cells with the cheapest preset (block or blinker) to grow.
  Field is mature oscillator at T2 with high reife:
    → evolve to attempt T3 promotion.
  Energy below 50 E and no affordable preset listed:
    → wait one tick and re-evaluate.
"""

_FALLBACK_AFFORDABLE_PRESETS: tuple[str, ...] = ("block", "blinker")
"""Used only if the backend's `affordable_presets` list is empty / missing.

Block (5 E) and Blinker (10 E) are the cheapest presets — safe defaults
that any agent with > 10 E can afford. The backend usually fills
`world_briefing.agent_situation.affordable_presets` itself; this fallback
is just defense for older backends or unexpected schema gaps.
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
    # Build the choice list once — used both to render the prompt and to
    # validate the LLM's response. Single source of truth: prompt and
    # validator can never disagree about what's actually offered.
    choices = _build_action_choices(agent.state)
    world = _format_world(agent.state, choices)

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
    params = decision["params"] or {}

    # Defense-in-depth layer 1 (S157 K1): drop actions outside the static
    # allowlist before they touch the Cosmergon API.
    if action not in VALID_ACTIONS:
        logger.warning(
            "llm emitted disallowed action %r — dropped (allowed: %s)",
            action,
            sorted(VALID_ACTIONS),
        )
        if on_decision is not None:
            on_decision("(disallowed)", {}, elapsed, False)
        return

    # Defense-in-depth layer 2 (S160): drop actions whose parameters
    # were not in the offered choice list. This is the structural fix
    # against UUID hallucination — small models will invent UUIDs even
    # when told not to. Filtering them locally never lets them reach
    # the backend (saves 404/422 noise + lets `wait`-fallback take over
    # next tick).
    if not _is_action_in_choices(action, params, choices):
        logger.warning(
            "llm action=%s params=%s not in offered choices — dropped (off-list)",
            action,
            _redact_params(params),
        )
        if on_decision is not None:
            on_decision("(off_list)", {}, elapsed, False)
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


def _make_choice(action: str, params: dict[str, Any], label: str) -> dict[str, Any]:
    """Build a choice dict including a ready-to-copy JSON snippet.

    The `json` field is the EXACT string the LLM should output for this
    line — pre-serialized so the model only has to copy it. Every line
    of the rendered prompt is paired with its own JSON, so there is
    nothing to "fill in" and no template-placeholders for a 3B model
    to literalize (S160 empirics: `<id-from-list>` was being copied
    verbatim from a placeholder example).
    """
    return {
        "action": action,
        "params": params,
        "label": label,
        "json": json.dumps({"action": action, "params": params}, separators=(",", ":")),
    }


def _build_action_choices(state: Any) -> list[dict[str, Any]]:
    """Build the explicit list of available actions for *this* state.

    Each entry: ``{"action": str, "params": dict, "label": str, "json": str}``.
    `label` is the human-readable line; `json` is the exact JSON output
    the LLM should emit for that line; `(action, params)` is what we
    accept back via the validator.

    This is the single source of truth for both the rendered prompt
    and the post-decision validator — they cannot disagree about what
    is actually offered.

    Coverage today:
      - place_cells × each owned field × each affordable preset
      - evolve × each owned field with entity_tier in 1..4 (T5 is max)
      - create_field × each owned cube (none for newcomers; structurally
        excluded so the LLM cannot hallucinate cube_ids)
      - wait (always)

    transfer_energy is intentionally not offered: a Free-Tier newcomer
    has no realistic recipient list in scope, and offering it without
    candidate counterparts only invites hallucinated player IDs.
    """
    choices: list[dict[str, Any]] = []
    if state is None:
        choices.append(_make_choice("wait", {}, "wait"))
        return choices

    fields = list(getattr(state, "fields", []) or [])
    own_cubes = list(getattr(state, "cubes", []) or [])

    wb = getattr(state, "world_briefing", None)
    sit = getattr(wb, "situation", None) if wb is not None else None
    affordable = list(getattr(sit, "affordable_presets", ()) or ())
    if not affordable:
        affordable = list(_FALLBACK_AFFORDABLE_PRESETS)

    # place_cells: one row per (field, affordable preset)
    for f in fields:
        fid = getattr(f, "id", None)
        if not fid:
            continue
        fid_str = str(fid)
        for preset in affordable:
            choices.append(
                _make_choice(
                    "place_cells",
                    {"field_id": fid_str, "preset": preset},
                    f"place_cells   field_id={fid_str}  preset={preset}",
                )
            )

    # evolve: one row per field that *could* level up (T1..T4)
    for f in fields:
        fid = getattr(f, "id", None)
        tier = getattr(f, "entity_tier", None)
        if fid and isinstance(tier, int) and 1 <= tier < 5:
            fid_str = str(fid)
            choices.append(
                _make_choice(
                    "evolve",
                    {"field_id": fid_str},
                    f"evolve        field_id={fid_str}  (current tier={tier})",
                )
            )

    # create_field: only for owned cubes (newcomers have none → not offered,
    # which prevents the cube_id hallucination loop seen in S160 empirics).
    for c in own_cubes:
        cid = getattr(c, "id", None)
        if cid:
            cid_str = str(cid)
            choices.append(
                _make_choice(
                    "create_field",
                    {"cube_id": cid_str},
                    f"create_field  cube_id={cid_str}",
                )
            )

    choices.append(_make_choice("wait", {}, "wait"))
    return choices


def _is_action_in_choices(
    action: str,
    params: dict[str, Any],
    choices: list[dict[str, Any]],
) -> bool:
    """True iff ``(action, params)`` exactly matches one offered choice.

    Param-equality is strict dict-equality — any extra/wrong key fails.
    For `wait`, params must be empty (matches the offered wait choice).
    """
    norm_params = params or {}
    for c in choices:
        if c["action"] == action and c["params"] == norm_params:
            return True
    return False


def _format_world(
    state: Any,
    choices: list[dict[str, Any]] | None = None,
) -> str:
    """Render world summary + numbered list of available actions for the LLM.

    Numbered, copy-from-list style is deliberate (S160): small models
    (3B class) reliably copy from an explicit list but routinely
    hallucinate UUIDs when asked to "use the field_id from above".
    """
    if state is None:
        return "(no state available — agent not yet connected)"

    if choices is None:
        choices = _build_action_choices(state)

    energy = getattr(state, "energy", "?")
    fields = list(getattr(state, "fields", []) or [])
    own_cubes = list(getattr(state, "cubes", []) or [])

    # Pull trigger-info from world_briefing.situation if available — these are
    # the signals that tell the LLM whether wait is rational or whether action
    # is needed (S160: without trigger-info qwen2.5:7b chose 100% wait at
    # 9988 E because the static energy number looks comfortable).
    wb = getattr(state, "world_briefing", None)
    sit = getattr(wb, "situation", None) if wb is not None else None
    energy_trend = getattr(sit, "energy_trend", "unknown") if sit is not None else "unknown"
    fields_without_cells = getattr(sit, "fields_without_cells", 0) if sit is not None else 0
    catastrophe = getattr(sit, "active_catastrophe", None) if sit is not None else None
    catastrophe_warn = getattr(sit, "catastrophe_warning_ticks", None) if sit is not None else None

    persona = getattr(state, "persona_type", "") or ""
    agent_name = getattr(state, "agent_name", "") or ""

    parts: list[str] = []
    if agent_name or persona:
        identity = f"You are {agent_name}".strip()
        if persona:
            identity += f", a {persona}-persona agent"
        parts.append(identity + ".")
        parts.append("")
    parts.extend(
        [
            "## Your situation",
            f"Energy: {energy} E (trend: {energy_trend})",
            f"Fields you own: {len(fields)}"
            + (f" ({fields_without_cells} empty — losing income)" if fields_without_cells else ""),
            f"Cubes you own: {len(own_cubes)}",
        ]
    )

    # Per-field detail: tier + cells + entity_type — lets the LLM reason about
    # tier-up eligibility (T2 oscillator → T3 needs spaceship pattern, etc.)
    for f in fields[:5]:
        fid = getattr(f, "id", "?")
        tier = getattr(f, "entity_tier", None)
        cells = getattr(f, "active_cell_count", 0)
        etype = getattr(f, "entity_type", None) or "?"
        fid_short = str(fid)[:8] + "..."
        parts.append(f"  - {fid_short}: T{tier} {etype}, {cells} live cells")

    if catastrophe:
        warn = f", impact in {catastrophe_warn} ticks" if catastrophe_warn else ""
        parts.append(f"⚠ Active catastrophe: {catastrophe}{warn}")

    parts.extend(
        [
            "",
            "## Available actions",
            "Pick exactly one line; output the JSON shown after the arrow verbatim.",
            "",
        ]
    )
    for i, c in enumerate(choices, 1):
        parts.append(f"{i:>2}. {c['label']}")
        parts.append(f"    → {c['json']}")
    parts.append("")
    parts.append("What is your move? Reply with only the JSON snippet.")
    return "\n".join(parts)
