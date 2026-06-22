#!/usr/bin/env python3
"""S163 A.2 Methoden-Pflicht — Local Pet-LLM-Bias Experiment Harness.

Runs Pet's actual prompt-builder + JSON-schema constraints against an
Ollama instance N times for a fixed mock state, dumps per-decision
JSONL, and prints an action-distribution summary.

Purpose: test ONE hypothesis at a time without touching live cobot.
S160/S162 lesson — Live-A/B-Hopping with 3 hypotheses produces phantom
bugs. Run this locally first.

Default mock state mirrors Comet-hand at S162-Empirie 18:50 UTC:
persona=scientist, balance=1.67M E, 1 Tier-2 oscillator field with
3 cells, no available evolve, no available create_field cube.

Usage:
    pip install -e ~/projekte/cosmergon-pet
    pip install -e ~/projekte/cosmergon-agent
    python scripts/local-experiment.py --runs 10

    # Override defaults:
    python scripts/local-experiment.py --runs 20 --persona warrior \
        --balance 50000 --model qwen2.5:7b \
        --ollama-url http://mac-mini.local:11434

The output JSONL is the same format the live-cobot dump uses (S163 A.2
extension), so the same downstream tooling works on either source.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

# Pet + SDK must be importable. `pip install -e .` in both repos.
from cosmergon_agent.state import GameState  # type: ignore

from cosmergon_pet.llm.ollama import OllamaProvider  # type: ignore
from cosmergon_pet.llm_decider import (  # type: ignore
    VALID_ACTIONS,
    _build_action_choices,
    _build_decision_schema,
    _build_system_prompt,
    _format_world,
    _is_action_in_choices,
)


def comet_hand_state(persona: str, balance: float) -> GameState:
    """Mock state reflecting Comet-hand at S162 18:50 UTC.

    Persona, balance and field-pattern reproduced from session-162-imac.md
    L1-Empirie. Single Tier-2 oscillator field, 3 cells, no eligible evolve.
    No free cubes available. Market-buyable defaults to empty so the
    persona-sequence falls through to its non-trade fallbacks.
    """
    field_id = "11111111-1111-1111-1111-111111111111"
    cube_id = "22222222-2222-2222-2222-222222222222"
    data = {
        "agent_id": "00000000-0000-0000-0000-000000000000",
        "agent_name": "comet-hand-mock",
        "persona_type": persona,
        "agent_type": "independent_agent",
        "agent_mode": "api",
        "subscription_tier": "free",
        "energy_balance": balance,
        "tick": 99999,
        "fields": [
            {
                "id": field_id,
                "cube_id": cube_id,
                "z_position": 0,
                "active_cell_count": 3,
                "entity_tier": 2,
                "entity_type": "oscillator",
                "reife_score": 7048,
                "permeability_state": "active",
            }
        ],
        "cubes": [
            {
                "id": cube_id,
                "name": "mock-cube",
                "cube_x": 0,
                "cube_y": 0,
                "cube_z": 0,
            }
        ],
        "universe_cubes": [],
        "ranking": {"score": 1234, "rank": 7, "total_players": 143},
        "focus": {"focus_energy": 100.0, "can_query_llm": True},
        "world_briefing": {
            "about": "Cosmergon mock state for local experiment.",
            "total_agents": 143,
            "your_rank": 7,
            "tip": "Local experiment — no live tip.",
            "agent_situation": {
                "energy_balance": balance,
                "affordable_presets": ["block", "blinker", "glider"],
                "fields_owned": 1,
                "cubes_owned": 1,
            },
            "market": {
                "summary": "0 buyable listings",
                "buyable": [],
            },
        },
        "reflection_due": False,
        "decisions_since_last_reflection": 0,
    }
    return GameState.from_api(data)


async def run_one_decision(
    provider: OllamaProvider,
    state: GameState,
    run_idx: int,
) -> dict:
    """Single decision round, mirroring _one_decision logic but inline.

    No agent.act — we don't want to mutate any live state.
    Returns a JSONL-shaped dict ready to write.
    """
    choices = _build_action_choices(state)
    world = _format_world(state, choices)
    schema = _build_decision_schema(choices)
    persona = state.persona_type or ""
    name = state.agent_name or ""
    system_prompt = _build_system_prompt(persona, name)
    memory = "(local experiment — no memory backend)"

    t0 = time.monotonic()
    raw_response = ""
    try:
        decision = await provider.decide(system_prompt, memory, world, schema=schema)
        raw_response = provider.last_raw_response or ""
        action = decision["action"]
        params = decision["params"] or {}
        if action not in VALID_ACTIONS:
            outcome = "disallowed"
        elif not _is_action_in_choices(action, params, choices):
            outcome = "off_list"
        elif action == "wait":
            outcome = "wait"
        else:
            outcome = "parsed"
    except Exception as e:
        action = "(provider_error)"
        params = {}
        outcome = "provider_error"
        raw_response = provider.last_raw_response or f"<exception: {e}>"
    elapsed = time.monotonic() - t0
    return {
        "phase": "outcome",
        "run_idx": run_idx,
        "timestamp": time.time(),
        "agent_id": state.agent_id,
        "persona": persona,
        "balance": state.energy,
        "n_choices": len(choices),
        "action": action,
        "params": params,
        "validation_outcome": outcome,
        "decided_in_seconds": round(elapsed, 3),
        "raw_response": raw_response,
        "provider_model": provider.model_string,
    }


async def main(args: argparse.Namespace) -> int:
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    state = comet_hand_state(args.persona, args.balance)
    provider = OllamaProvider(url=args.ollama_url, model=args.model)

    print(
        f"[local-experiment] persona={args.persona} balance={args.balance:.0f} "
        f"model={provider.model_string} url={provider.url} runs={args.runs}",
        file=sys.stderr,
    )
    print(f"[local-experiment] output={output}", file=sys.stderr)

    actions: Counter[str] = Counter()
    outcomes: Counter[str] = Counter()
    elapsed_samples: list[float] = []

    with output.open("w") as f:
        for i in range(args.runs):
            entry = await run_one_decision(provider, state, run_idx=i)
            f.write(json.dumps(entry, default=str) + "\n")
            actions[entry["action"]] += 1
            outcomes[entry["validation_outcome"]] += 1
            elapsed_samples.append(entry["decided_in_seconds"])
            print(
                f"  run {i + 1:2d}/{args.runs}: {entry['action']:<20s} "
                f"outcome={entry['validation_outcome']:<14s} "
                f"in {entry['decided_in_seconds']:.1f}s",
                file=sys.stderr,
            )

    print("\n=== Action-Distribution ===", file=sys.stderr)
    for action, count in actions.most_common():
        print(f"  {action:<20s} {count:3d} ({count * 100 // args.runs}%)", file=sys.stderr)
    print("\n=== Validation-Outcome ===", file=sys.stderr)
    for outcome, count in outcomes.most_common():
        print(f"  {outcome:<20s} {count:3d}", file=sys.stderr)
    if elapsed_samples:
        print(
            f"\n=== Latency (sec) === median={statistics.median(elapsed_samples):.2f} "
            f"min={min(elapsed_samples):.2f} max={max(elapsed_samples):.2f}",
            file=sys.stderr,
        )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--persona", default="scientist")
    parser.add_argument("--balance", type=float, default=1_671_088.0)
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434",
        help="Ollama base URL (default: http://localhost:11434)",
    )
    parser.add_argument(
        "--output",
        default=f"/tmp/local-experiment-{int(time.time())}.jsonl",
    )
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    sys.exit(asyncio.run(main(args)))
