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
import os
import time
from pathlib import Path
from typing import Any

from cosmergon_agent import CosmergonAgent

from .agent_state import StateSource
from .face import EVOLUTION_ENERGY_COST, REIFE_THRESHOLDS, TIER_REQUIRED_TYPE
from .llm import LLMProvider, LLMProviderError

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_S = 60.0
"""Default seconds between LLM decisions. Matches the Cosmergon tick (60 s)."""


VALID_ACTIONS: frozenset[str] = frozenset(
    {
        "place_cells",
        "evolve",
        "create_field",
        "create_cube",
        "transfer_energy",
        "market_list",
        "market_buy",
        "propose_contract",
        # S204 — eingehende Verträge entscheiden + countern
        "accept_contract",
        "reject_contract",
        "propose_counter",
        # S206 — Marauder-Mission-System Phase 2 + Item-Pickups
        "start_mission",
        "cancel_mission",
        "collect_spore",
        "shoot_spore",
        "pickup_drop",
        "transfer_inventory",
        "place_deployable",
        "claim_field",
        "heal_holes",
        "terminal_query",
        "propose_from_template",
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

# S165: Free-tier-allowed contract types. Backend (`agent_game.py
# ::_FREE_CONTRACT_TYPES`) rejects others with HTTP 402. Keep in sync.
# Developer/Enterprise tiers may also propose `tribute` and `alliance`
# but the Pet targets Maker (Free) usage, so we surface only the safe set.
_FREE_CONTRACT_TYPES: tuple[str, ...] = ("non_aggression", "trade_agreement")

# Default terms per contract type. Backend requires the field but accepts
# any JSON object whose shape matches the contract semantics. We use a
# conservative duration so a misclick doesn't lock the agent for long.
_CONTRACT_TERM_TEMPLATES: dict[str, dict[str, Any]] = {
    "non_aggression": {"duration_ticks": 100},
    "trade_agreement": {"duration_ticks": 100},
}

# Minimum balance before propose_contract is offered. Below this the
# agent is in sustain mode and a contract commitment is premature.
_PROPOSE_CONTRACT_MIN_BALANCE: float = 5_000.0

# Max counterparts surfaced per tick — keeps the schema small for 3B-LLMs
# even if backend ever raises the briefing cap above 5.
_PROPOSE_CONTRACT_MAX_TARGETS: int = 5


_PERSONA_GUIDANCE: dict[str, dict[str, Any]] = {
    "scientist": {
        "tone": (
            "You are methodical and curious. You treat each tick as an experiment: "
            "grow your fields steadily, evolve them when they mature, document outcomes."
        ),
        "sequence": (
            "WHEN to act (pick the FIRST condition that matches):\n"
            "  - IF any evolve line is offered: pick that evolve line. "
            "Tier-jump doubles output — scientist's prime move.\n"
            "  - IF energy >= 100000 AND any market_buy line is offered for under 2000 E: "
            "pick the cheapest market_buy line — acquire blueprint to test.\n"
            "  - IF energy < 1500: pick place_cells with cheapest preset (block). "
            "Sustain mode — DO NOT market_buy here.\n"
            "  - IF energy >= 100000 AND a market_list line is offered: "
            "pick a market_list line — publish surplus, fund future experiments.\n"
            "  - IF energy >= 50000 AND a propose_contract line with "
            "type=trade_agreement is offered: pick that propose_contract line "
            "— controlled cooperation experiment.\n"
            "  - IF energy >= 30000 AND a create_field line is offered: "
            "pick create_field — start a new experiment.\n"
            "  - ELSE IF a place_cells line is offered: pick the line with the FEWEST live cells.\n"
            "  - ELSE: pick wait."
        ),
        "examples": (
            "  Energy 1.5M, an evolve line for tier-2 field is offered:\n"
            "    → pick the evolve line (Pfad 1, prime move).\n"
            "  Energy 800k, no evolve, no market_buy under 2000 E, market_list line offered:\n"
            "    → pick a market_list line (Pfad 4, publish surplus).\n"
            "  Energy 80k, no evolve/market_buy/market_list, "
            "propose_contract trade_agreement offered:\n"
            "    → pick that propose_contract line (Pfad 5, cooperation experiment)."
        ),
    },
    "warrior": {
        "tone": (
            "You are aggressive and expansionist. You grow fast, claim ground, "
            "and never let an opportunity to add cells pass."
        ),
        "sequence": (
            "WHEN to act (pick the FIRST condition that matches):\n"
            "  - IF any place_cells line is offered AND that field has < 30 cells: "
            "pick place_cells (FEWEST cells) — close the gap.\n"
            "  - IF any evolve line is offered: pick evolve — each tier ~doubles output.\n"
            "  - IF a create_field line is offered AND energy >= 5000: "
            "pick create_field — claim more territory.\n"
            "  - IF a market_buy line is offered for under 2000 E: "
            "pick market_buy — buy yourself an edge.\n"
            "  - IF energy >= 50000 AND a propose_contract line with "
            "type=non_aggression is offered: pick that propose_contract line "
            "— buy peace on one flank, free up forces.\n"
            "  - ELSE IF a place_cells line is offered: pick place_cells (FEWEST cells).\n"
            "  - ELSE: pick wait."
        ),
        "examples": (
            "  A field with only 12 cells offers a place_cells line:\n"
            "    → pick that place_cells line (Pfad 1, close the gap).\n"
            "  All fields full (>30 cells), an evolve line is offered:\n"
            "    → pick the evolve line (Pfad 2, doubles output).\n"
            "  All fields full, no evolve, energy 30k, create_field line offered:\n"
            "    → pick a create_field line (Pfad 3, claim territory).\n"
            "  Fields full, no evolve/create/buy, energy 80k, "
            "propose_contract non_aggression offered:\n"
            "    → pick that propose_contract line (Pfad 5, secure flank)."
        ),
    },
    "diplomat": {
        "tone": (
            "You are patient and relationship-focused, but you still maintain your own "
            "fields — a diplomat without resources has no leverage."
        ),
        "sequence": (
            "WHEN to act (pick the FIRST condition that matches):\n"
            "  - IF energy < 1000: pick place_cells (cheapest preset). Sustain mode.\n"
            "  - IF energy >= 10000 AND any propose_contract line is offered: "
            "pick a propose_contract line — relationships are the diplomat's prime move. "
            "Prefer non_aggression to stabilise neighbours, trade_agreement to bind partners.\n"
            "  - IF a market_buy line is offered for under 1500 E: pick market_buy. "
            "Quiet trades signal goodwill.\n"
            "  - IF a market_list line is offered AND energy >= 30000: "
            "pick market_list. Trades build relationships.\n"
            "  - IF any evolve line is offered: pick evolve.\n"
            "  - IF a create_field line is offered AND energy >= 5000: pick create_field.\n"
            "  - ELSE IF a place_cells line is offered: pick place_cells (FEWEST cells).\n"
            "  - ELSE: pick wait."
        ),
        "examples": (
            "  Energy 800, place_cells line with cheapest preset offered:\n"
            "    → pick that place_cells line (Pfad 1, sustain mode).\n"
            "  Energy 30k, propose_contract non_aggression offered:\n"
            "    → pick that propose_contract line (Pfad 2, prime move).\n"
            "  Energy 50k, no contract offered, market_buy line under 1500 E offered:\n"
            "    → pick the market_buy line (Pfad 3, goodwill trade)."
        ),
    },
    "farmer": {
        "tone": (
            "You are steady, patient, and incremental. You build slowly but reliably, "
            "topping up fields tick by tick."
        ),
        "sequence": (
            "WHEN to act (pick the FIRST condition that matches):\n"
            "  - IF any field has < 50 cells AND a place_cells line is offered for it: "
            "pick that place_cells (toad if affordable, blinker otherwise). Top up.\n"
            "  - IF a market_list line is offered AND energy >= 50000: "
            "pick market_list — sell surplus, the farmer's natural action.\n"
            "  - IF any evolve line is offered: pick evolve — harvest the upgrade.\n"
            "  - IF a market_buy line is offered for under 500 E: "
            "pick market_buy. Cheap blueprint.\n"
            "  - IF energy >= 80000 AND a propose_contract line with "
            "type=non_aggression is offered: pick that propose_contract line "
            "— stable neighbours protect a long harvest.\n"
            "  - IF a create_field line is offered AND energy >= 10000: pick create_field.\n"
            "  - ELSE IF a place_cells line is offered: pick place_cells (FEWEST cells).\n"
            "  - ELSE: pick wait — farmer is patient, accumulation over action."
        ),
        "examples": (
            "  A field with 30 cells (under 50 threshold), place_cells line offered:\n"
            "    → pick that place_cells line (Pfad 1, top up).\n"
            "  All fields full (>50 cells), energy 80k, market_list line offered:\n"
            "    → pick a market_list line (Pfad 2, sell surplus).\n"
            "  All fields full, no market_list, evolve line offered:\n"
            "    → pick the evolve line (Pfad 3, harvest upgrade).\n"
            "  All fields full, energy 100k, no market/evolve, "
            "propose_contract non_aggression offered:\n"
            "    → pick that propose_contract line (Pfad 5, stable neighbour)."
        ),
    },
    "expansionist": {
        "tone": (
            "You spread wide. More cubes, more fields, more presence. "
            "Acquisition over consolidation."
        ),
        "sequence": (
            "WHEN to act (pick the FIRST condition that matches):\n"
            "  - IF a create_field line is offered AND energy >= 5000: "
            "pick create_field — claim the cube, expansionist's flagship.\n"
            "  - IF a market_buy line is offered for under 2000 E (cheaper than self-built field): "
            "pick market_buy — every acquisition counts.\n"
            "  - IF any place_cells line is offered AND that field has < 30 cells: "
            "pick place_cells — bootstrap new fields.\n"
            "  - IF any evolve line is offered: pick evolve.\n"
            "  - IF energy >= 50000 AND a propose_contract line with "
            "type=non_aggression is offered: pick that propose_contract line "
            "— clear a flank, expansion needs an open road.\n"
            "  - IF a market_list line is offered AND energy >= 100000: "
            "pick market_list. Fund expansion.\n"
            "  - ELSE IF a place_cells line is offered: pick place_cells (FEWEST cells).\n"
            "  - ELSE: pick wait."
        ),
        "examples": (
            "  Energy 20k, a create_field line is offered:\n"
            "    → pick the create_field line (Pfad 1, flagship move).\n"
            "  Energy 1M, no create_field offered, market_buy line under 2000 E offered:\n"
            "    → pick the market_buy line (Pfad 2, cheap acquisition).\n"
            "  All cubes full, place_cells line for field with 12 cells offered:\n"
            "    → pick that place_cells line (Pfad 3, bootstrap).\n"
            "  No create/market_buy/place_cells, energy 70k, "
            "propose_contract non_aggression offered:\n"
            "    → pick that propose_contract line (Pfad 5, clear a flank)."
        ),
    },
    "trader": {
        "tone": (
            "You read the market. Your edge is timing, not territory. "
            "Buy low, list high, accumulate capital."
        ),
        "sequence": (
            "WHEN to act (pick the FIRST condition that matches):\n"
            "  - IF a market_buy line is offered AND its price is under energy * 0.1: "
            "pick the cheapest market_buy — trader's primary move.\n"
            "  - IF a market_list line is offered AND energy >= 30000: "
            "pick market_list — monetise inventory.\n"
            "  - IF energy >= 30000 AND a propose_contract line with "
            "type=trade_agreement is offered: pick that propose_contract line "
            "— locking in regular flow is trader's specialty.\n"
            "  - IF energy < 1000: pick place_cells (cheapest preset). Keep base alive.\n"
            "  - IF any evolve line is offered: pick evolve.\n"
            "  - IF a create_field line is offered AND energy >= 10000: pick create_field.\n"
            "  - ELSE IF a place_cells line is offered: pick place_cells (FEWEST cells).\n"
            "  - ELSE: pick wait."
        ),
        "examples": (
            "  Energy 100k, market_buy line at 8000 E (= 8% of energy, under 10%) offered:\n"
            "    → pick the market_buy line (Pfad 1, primary move).\n"
            "  Energy 50k, no cheap market_buy, market_list line offered:\n"
            "    → pick a market_list line (Pfad 2, monetise inventory).\n"
            "  Energy 50k, no market_buy, no market_list, "
            "propose_contract trade_agreement offered:\n"
            "    → pick that propose_contract line (Pfad 3, lock in flow).\n"
            "  Energy 500, place_cells with cheapest preset offered:\n"
            "    → pick that place_cells line (Pfad 4, keep base alive)."
        ),
    },
}
_DEFAULT_PERSONA = "scientist"


def _build_system_prompt(persona_type: str, agent_name: str) -> str:
    """Persona-aware system prompt — analogous to NPC ``personas.build_system_prompt``.

    The NPC path (``backend/app/core/personas.py``) gives every llm-Agent a
    persona-tone block + a numbered preferred-action sequence. NPCs follow
    that sequence reliably (S160 empirics: 67% place_cells, 20% wait over
    225 decisions in 2h). The Pet had only a generic catalog and chose
    100% wait.

    This builder mirrors the NPC structure for the Pet's restricted action
    vocabulary (``VALID_ACTIONS``). Persona is passed in from
    ``state.persona_type``; unknown personas fall back to scientist.
    """
    guidance = _PERSONA_GUIDANCE.get(persona_type) or _PERSONA_GUIDANCE[_DEFAULT_PERSONA]
    name = agent_name or "an autonomous agent"
    persona_label = persona_type or _DEFAULT_PERSONA
    examples = guidance.get("examples") or _FALLBACK_EXAMPLES
    return f"""You are {name}, a {persona_label}-persona agent in Cosmergon —
a Conway's Game of Life economy. Every ~60 seconds you take a turn.

Your personality:
  {guidance["tone"]}

Preferred action sequence (try in this order — pick the first that applies this tick):
  {guidance["sequence"]}

Why not wait:
  Energy decays every tick. Doing nothing means losing energy slowly until
  you die. A healthy {persona_label} is always growing somewhere. Wait is
  the fallback for ticks where no growth move is on the list — not a
  default.

How to answer:
  Each numbered line in "Available actions" IS a complete JSON object.
  Pick exactly ONE line and output that line's JSON verbatim — character
  for character, including all UUIDs. Output ONLY that JSON, nothing else.
  No markdown fences. No comments. No newly-built objects.

Decision examples (your persona's typical patterns):
{examples}
  Only "wait" is in the list (no growth moves possible):
    → pick the wait line.
"""


# Fallback used only if a persona's `examples` key is missing — e.g. if
# a future persona is added without examples. Kept generic so we never
# render a broken prompt. S162 P1-FAIL-Diagnose: hard-coded examples for
# place_cells/evolve previously biased Comet-hand to 99% place_cells even
# when scientist-Pfad-5 (create_field) should have fired.
_FALLBACK_EXAMPLES: str = (
    "  Energy is healthy and at least one growth-move line is offered:\n"
    "    → pick the line that matches the FIRST condition in your sequence.\n"
    "  No growth-move offered:\n"
    "    → pick the place_cells line for the field with the FEWEST live cells."
)


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
    # One instance for the whole loop — its counter decides when a missing
    # state stops being a hiccup and becomes worth a warning (S306).
    state_source = StateSource()
    logger.info(
        "llm_decision_loop started provider=%s model=%s interval=%.1fs",
        provider.name,
        provider.model_string,
        interval_s,
    )
    while not stop.is_set():
        try:
            await _one_decision(agent, provider, on_decision, state_source)
        except Exception:
            # Catch-all: nothing in this loop is allowed to kill the Pet.
            logger.warning("llm_decision_loop iteration failed", exc_info=True)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_s)
        except asyncio.TimeoutError:
            continue
    logger.info("llm_decision_loop stopped")


_DUMP_ENV_VAR = "COSMERGON_PET_PROMPT_DUMP_PATH"


def _maybe_dump_prompt(
    agent: CosmergonAgent,
    system_prompt: str,
    memory: str,
    world: str,
    schema: dict[str, Any],
) -> None:
    """Optional diagnostic: dump the LLM input 4-tuple to a JSONL file.

    Activated only when ``COSMERGON_PET_PROMPT_DUMP_PATH`` env var is set
    to a writable file path. Each call appends one JSON object per line:
    ``{timestamp, agent_id, system_prompt, memory, world, schema}``.

    Off by default — no file I/O when env var is unset. Designed for
    targeted diagnosis (compare Pet's LLM input against an in-Cosmergon
    NPC's LLM input for the same game state); not meant for permanent
    logging. Token-free by construction: only inputs to ``provider.decide``
    are written; player-token never touches this path.

    Failures are logged at WARNING and swallowed — diagnostic must not
    affect the decision loop.
    """
    dump_path_str = os.environ.get(_DUMP_ENV_VAR)
    if not dump_path_str:
        return
    try:
        dump_path = Path(dump_path_str)
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        agent_id = getattr(agent.state, "agent_id", None) or getattr(agent.state, "id", None)
        entry = {
            "phase": "input",
            "timestamp": time.time(),
            "agent_id": str(agent_id) if agent_id else "",
            "system_prompt": system_prompt,
            "memory": memory,
            "world": world,
            "schema": schema,
        }
        with dump_path.open("a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:
        logger.warning("prompt-dump failed", exc_info=True)


def _maybe_dump_decision_outcome(
    agent: CosmergonAgent,
    provider: LLMProvider,
    action: str,
    params: dict[str, Any],
    validation_outcome: str,
    success: bool | None,
    decided_in_seconds: float,
) -> None:
    """Optional diagnostic: dump decision outcome (S163 A.2 Methoden-Pflicht).

    Companion to ``_maybe_dump_prompt``. Same JSONL file, same env var.
    Each pre/outcome pair correlates by timestamp order (input first,
    then outcome).

    Captures the verbatim model output (``provider.last_raw_response``,
    if the provider exposes it) plus the validation path the action took:
      ``parsed``        — parsed JSON, before any validation
      ``disallowed``    — action not in VALID_ACTIONS
      ``off_list``      — action+params not in offered choices
      ``wait``          — model chose to wait
      ``agent_act_ok``  — backend accepted the action
      ``agent_act_fail``— backend rejected the action
      ``provider_error``— provider raised before returning a decision

    Off by default. Activated only when the env var is set. Failures
    are logged at WARNING and swallowed — diagnosis must not affect
    the decision loop.
    """
    dump_path_str = os.environ.get(_DUMP_ENV_VAR)
    if not dump_path_str:
        return
    try:
        dump_path = Path(dump_path_str)
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        agent_id = getattr(agent.state, "agent_id", None) or getattr(agent.state, "id", None)
        raw_response = getattr(provider, "last_raw_response", None)
        entry = {
            "phase": "outcome",
            "timestamp": time.time(),
            "agent_id": str(agent_id) if agent_id else "",
            "action": action,
            "params": _redact_params(params) if params else {},
            "validation_outcome": validation_outcome,
            "success": success,
            "decided_in_seconds": round(decided_in_seconds, 3),
            "raw_response": raw_response,
            "provider_model": getattr(provider, "model_string", str(provider)),
        }
        with dump_path.open("a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:
        logger.warning("decision-outcome-dump failed", exc_info=True)


async def _maybe_reflect(
    agent: CosmergonAgent,
    provider: LLMProvider,
) -> None:
    """If `state.reflection_due` is set, run one reflection round.

    Logged but does not raise — reflection failures must never break
    the decision loop. Calls `agent.fetch_reflection_signals` →
    `provider.reflect` → `agent.post_reflection` and returns silently
    when any step yields no result. The Pet retries next tick if the
    backend still flags `reflection_due`.

    Older backends (< v1.60.862) leave `reflection_due` at the SDK's
    default `False`, so this is a safe no-op there.
    """
    state = agent.state
    if state is None or not getattr(state, "reflection_due", False):
        return
    fetch = getattr(agent, "fetch_reflection_signals", None)
    post = getattr(agent, "post_reflection", None)
    if fetch is None or post is None:
        return  # SDK too old (< v0.10.0) — endpoints not exposed
    try:
        signals = await fetch(horizon="short")
    except Exception:
        logger.warning("reflection: signals fetch failed", exc_info=True)
        return
    if not signals:
        return
    if not signals.get("top_5") and not signals.get("bottom_5"):
        return  # nothing to reflect on yet
    persona = getattr(state, "persona_type", "") or ""
    name = getattr(state, "agent_name", "") or ""
    try:
        result = await provider.reflect(signals, persona, name)
    except Exception:
        logger.warning("reflection: provider.reflect raised", exc_info=True)
        return
    if not result:
        return
    try:
        await post(
            lessons=result["lessons"],
            avoid=result["avoid"],
            double_down=result["double_down"],
            since_tick=int(signals.get("since_tick", 0)),
            horizon=signals.get("horizon", "short"),
            model_used=getattr(provider, "model_string", None),
        )
        logger.info(
            "reflection: persisted (model=%s, decisions=%s)",
            getattr(provider, "model_string", "?"),
            signals.get("decisions_in_window", "?"),
        )
    except Exception:
        logger.warning("reflection: post failed", exc_info=True)


async def _one_decision(
    agent: CosmergonAgent,
    provider: LLMProvider,
    on_decision: callable | None,  # type: ignore[type-arg]
    state_source: StateSource | None = None,
) -> None:
    """Single decision round. Logged but does not raise."""
    # S306: obtain the state before using it. Previously `agent.state` went
    # unchecked into `_build_action_choices`, which then collapsed to the
    # `wait` line only — the exact failure diagnosed on 2026-05-04 and patched
    # back then by mirroring into the SDK's private slot from `face.py`.
    # Without a state there is nothing to decide, so skip the round rather
    # than ask the model about an empty world.
    source = state_source or StateSource()
    state = await source.current(agent)
    if state is None:
        return
    # Reflection runs BEFORE the decision so the upcoming LLM call sees
    # a memory-prompt that already includes the freshly-written
    # self_reflection (importance=1.0 → renderer's "## Your Past Lessons"
    # block picks it up). Order matters: reflect → fetch_memory → decide.
    await _maybe_reflect(agent, provider)
    memory = await _safe_memory(agent)
    # Build the choice list once — used both to render the prompt, to
    # constrain the LLM via JSON-Schema, and to validate the response.
    # Single source of truth: prompt + schema + validator can never
    # disagree about what is actually offered.
    choices = _build_action_choices(state)
    world = _format_world(state, choices)
    schema = _build_decision_schema(choices)
    persona = getattr(state, "persona_type", "") or ""
    name = getattr(state, "agent_name", "") or ""
    system_prompt = _build_system_prompt(persona, name)

    _maybe_dump_prompt(agent, system_prompt, memory, world, schema)

    t0 = time.monotonic()
    try:
        decision = await provider.decide(system_prompt, memory, world, schema=schema)
    except LLMProviderError as e:
        elapsed = time.monotonic() - t0
        logger.warning("provider %s failed: %s", provider.name, e)
        _maybe_dump_decision_outcome(
            agent, provider, "(provider_error)", {}, "provider_error", False, elapsed
        )
        if on_decision is not None:
            on_decision("(provider_error)", {}, elapsed, False)
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
        _maybe_dump_decision_outcome(agent, provider, action, params, "disallowed", False, elapsed)
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
        _maybe_dump_decision_outcome(agent, provider, action, params, "off_list", False, elapsed)
        if on_decision is not None:
            on_decision("(off_list)", {}, elapsed, False)
        return

    if action == "wait":
        logger.info("llm chose wait (%.1fs)", elapsed)
        _maybe_dump_decision_outcome(agent, provider, "wait", {}, "wait", True, elapsed)
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
    _maybe_dump_decision_outcome(
        agent,
        provider,
        action,
        params,
        "agent_act_ok" if success else "agent_act_fail",
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

    # evolve: one row per field that meets ALL backend can-evolve criteria.
    # Mirrors `face.py::_find_evolvable_field` / backend
    # `agent_game._handle_evolve` (tier, reife, entity_type, balance).
    # Conservative — does NOT consider `field.field_metadata.max_tier_paid`
    # (free re-evolution after devolve, S111-fix). Effect: Pet may skip
    # offering an evolve choice that would actually be free; it never
    # offers a choice the backend would reject. Symptoms when filters were
    # missing (S163/S164 empirie): 30/30 backend-400 with "Entity not
    # mature enough" or "Pattern type does not match target tier".
    balance = float(getattr(state, "energy", 0) or 0)
    for f in fields:
        fid = getattr(f, "id", None)
        tier = getattr(f, "entity_tier", None) or 0
        if not fid or not isinstance(tier, int) or tier <= 0 or tier >= 5:
            continue
        next_tier = tier + 1
        reife = getattr(f, "reife_score", None) or 0
        if reife < REIFE_THRESHOLDS.get(next_tier, 999_999):
            continue
        required_type = TIER_REQUIRED_TYPE.get(next_tier)
        if required_type and getattr(f, "entity_type", None) != required_type:
            continue
        cost = EVOLUTION_ENERGY_COST.get(tier, 0)
        if balance < cost:
            continue
        fid_str = str(fid)
        choices.append(
            _make_choice(
                "evolve",
                {"field_id": fid_str},
                f"evolve        field_id={fid_str}  (T{tier}->T{next_tier}, cost={cost} E)",
            )
        )

    # create_field: every cube in the universe is fair game — Cosmergon's
    # backend allows any agent to add a field to any cube (cube ownership is
    # an affiliate marker, not an access gate). Pre-S161 we only offered own
    # cubes, which structurally locked newcomers (no cube → no growth path)
    # and was the wrong fix for the S160 hallucination problem; the real
    # safeguard is that every cube_id we surface here is a real backend UUID
    # from `state.universe_cubes`, so the LLM cannot invent IDs anyway.
    universe_cubes = list(getattr(state, "universe_cubes", []) or [])
    for c in universe_cubes:
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

    # market_list: offered when the agent has a meaningful energy surplus.
    # Three price-tiers so the LLM picks based on its own urgency: cheap
    # (400 = vagant floor — moves fast), market (450 — middle), patient
    # (500 — accept slower fill for more value). Backend (S161, KAT-B)
    # defaults item_type='energy' so we don't have to pass it.
    energy = float(getattr(state, "energy", 0) or 0)
    if energy >= 1500:
        for price in (400.0, 450.0, 500.0):
            choices.append(
                _make_choice(
                    "market_list",
                    {"price_energy": price},
                    f"market_list   price_energy={price}",
                )
            )

    # market_buy: one branch per affordable listing. Uses
    # state.world_briefing.market.buyable from backend ≥ v1.60.866 — the
    # listing_id goes in as a const, so the LLM cannot invent UUIDs.
    # Filtered to listings the agent can actually pay for; capped at 10
    # to keep the schema small for 3B-LLMs even when the backend
    # surfaces 20.
    market = getattr(wb, "market", None) if wb is not None else None
    buyable = list(getattr(market, "buyable", ()) or ())
    affordable_buyable = [b for b in buyable if float(getattr(b, "price_energy", 0)) <= energy]
    for entry in affordable_buyable[:10]:
        listing_id = getattr(entry, "listing_id", None)
        if not listing_id:
            continue
        item_type = getattr(entry, "item_type", "?")
        price = float(getattr(entry, "price_energy", 0))
        choices.append(
            _make_choice(
                "market_buy",
                {"listing_id": str(listing_id)},
                f"market_buy    listing_id={listing_id}  ({item_type} for {price:.0f} E)",
            )
        )

    # propose_contract: one branch per (target × free-tier contract_type).
    # Uses state.world_briefing.contract_targets from backend ≥ S165 — the
    # to_player_id goes in as a const, so the LLM cannot invent UUIDs.
    # Gated on a minimum balance so a sustain-mode agent doesn't enter
    # commitments. Backend `_FREE_CONTRACT_TYPES` is the source of truth
    # for which types Free agents may propose; we mirror it in
    # `_FREE_CONTRACT_TYPES` (above) and keep them in sync.
    targets = list(getattr(wb, "contract_targets", ()) or []) if wb is not None else []
    if energy >= _PROPOSE_CONTRACT_MIN_BALANCE and targets:
        for target in targets[:_PROPOSE_CONTRACT_MAX_TARGETS]:
            tid = getattr(target, "player_id", None)
            tname = getattr(target, "username", "?") or "?"
            if not tid:
                continue
            tid_str = str(tid)
            for ctype in _FREE_CONTRACT_TYPES:
                terms = dict(_CONTRACT_TERM_TEMPLATES[ctype])
                choices.append(
                    _make_choice(
                        "propose_contract",
                        {
                            "to_player_id": tid_str,
                            "contract_type": ctype,
                            "terms": terms,
                            "escrow_amount": 0,
                        },
                        f"propose_contract  to={tname}  type={ctype}",
                    )
                )

    # S204 — eingehende Verträge: pro pending contract eine accept- und eine reject-Zeile.
    # state.pending_contracts wird vom SDK gefüllt (siehe cosmergon_agent.state.pending_contracts).
    pending = list(getattr(state, "pending_contracts", []) or [])
    for c in pending[:5]:  # Cap 5 — Prompt-Größe für 3B-LLMs schonend halten
        cid = c.get("contract_id") if isinstance(c, dict) else getattr(c, "contract_id", None)
        ctype = c.get("contract_type") if isinstance(c, dict) else getattr(c, "contract_type", None)
        if not cid or not ctype:
            continue
        cid_str = str(cid)
        choices.append(
            _make_choice(
                "accept_contract",
                {"contract_id": cid_str, "escrow_amount": 0.0},
                f"accept_contract  id={cid_str}  type={ctype}",
            )
        )
        choices.append(
            _make_choice(
                "reject_contract",
                {"contract_id": cid_str},
                f"reject_contract  id={cid_str}  type={ctype}",
            )
        )

    choices.append(_make_choice("wait", {}, "wait"))
    return choices


def _build_decision_schema(choices: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a JSON-Schema that constrains the LLM output to one of the offered choices.

    Each choice becomes one branch of a `oneOf` discriminator, with `action`
    pinned via `const` and every parameter pinned to its exact value via
    `const` again. The model is therefore forced — at decoder level — to
    produce a JSON object that matches one of the lines we offered. There
    is no way for the model to reply with `{"action":"place_cells","params":{}}`
    or to invent a UUID; those simply aren't in the schema.

    Requires Ollama ≥ Q1/2025 (structured-output release). Other providers
    that accept JSON-Schema (OpenAI tool-use, Anthropic) get the same
    schema. Providers that don't support schemas treat it as advisory.
    """
    if not choices:
        return {}
    return {
        "type": "object",
        "oneOf": [
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["action", "params"],
                "properties": {
                    "action": {"const": c["action"]},
                    "params": _params_schema(c["params"]),
                },
            }
            for c in choices
        ],
    }


def _params_schema(params: dict[str, Any]) -> dict[str, Any]:
    """Per-action params sub-schema: every key pinned via `const`."""
    if not params:
        return {"type": "object", "additionalProperties": False, "properties": {}}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(params.keys()),
        "properties": {k: {"const": v} for k, v in params.items()},
    }


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
    universe_cubes = list(getattr(state, "universe_cubes", []) or [])

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
            f"Cubes you own: {len(own_cubes)}"
            + (
                f" — {len(universe_cubes)} cubes available universe-wide for create_field"
                if len(universe_cubes) > len(own_cubes)
                else ""
            ),
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
            "Each line below is a complete JSON object.",
            "Output exactly ONE of these lines verbatim — nothing else.",
            "",
        ]
    )
    for i, c in enumerate(choices, 1):
        # Each line is a self-contained JSON object the LLM should copy 1:1.
        # The trailing comment after `//` is for human-readability only; the
        # LLM is told to copy the JSON portion. Most JSON parsers (and our
        # downstream `json.loads`) reject `//`, so we strip the comment by
        # putting it after the JSON terminator.
        parts.append(f"{i:>2}. {c['json']}    // {c['label']}")
    parts.append("")
    parts.append("Your move? Output one of the JSON objects above, exactly.")
    return "\n".join(parts)
