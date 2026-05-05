"""Tests for the Pet LLM decision loop.

Provider + agent are mocked. Verifies:
  - happy path: provider decision triggers agent.act with right params
  - wait-action: no agent.act call
  - provider error: pet stays alive, no exception leaked
  - on_decision callback fires for each outcome class
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock


def _import_or_skip() -> Any:
    try:
        from cosmergon_pet import llm_decider  # noqa: F401
    except Exception:
        try:
            import pytest  # type: ignore[import-not-found]
        except Exception:
            print("SKIP  cosmergon_pet.llm_decider not importable", file=sys.stderr)
            sys.exit(0)
        pytest.skip("cosmergon_pet.llm_decider not importable")
    from cosmergon_pet import llm_decider as mod

    return mod


def _make_state(
    *,
    energy: float = 1000.0,
    field_ids: list[tuple[str, int]] | None = None,
    cube_ids: list[str] | None = None,
    universe_cube_ids: list[str] | None = None,
    affordable_presets: tuple[str, ...] = ("block", "blinker"),
) -> MagicMock:
    """Build a fake GameState with explicit fields/cubes/presets.

    `field_ids`: list of (id, tier). `cube_ids`: own cube IDs.
    `universe_cube_ids`: cube IDs available in the universe (for create_field
    via state.universe_cubes; defaults to cube_ids when not given).
    The returned mock matches the SDK GameState attribute shape used by
    `_build_action_choices` and `_format_world`.
    """
    state = MagicMock()
    state.energy = energy
    state.fields = []
    for fid, tier in field_ids or []:
        f = MagicMock()
        f.id = fid
        f.entity_tier = tier
        f.active_cell_count = 3
        f.reife_score = 100
        state.fields.append(f)
    state.cubes = []
    for cid in cube_ids or []:
        c = MagicMock()
        c.id = cid
        state.cubes.append(c)
    state.universe_cubes = []
    for cid in universe_cube_ids if universe_cube_ids is not None else (cube_ids or []):
        c = MagicMock()
        c.id = cid
        state.universe_cubes.append(c)
    sit = MagicMock()
    sit.affordable_presets = affordable_presets
    wb = MagicMock()
    wb.situation = sit
    state.world_briefing = wb
    return state


def _make_agent(state: Any = None, act_success: bool = True) -> MagicMock:
    """Mock agent with fetch_memory_prompt + act + state."""
    agent = MagicMock()
    agent.state = state
    agent.fetch_memory_prompt = AsyncMock(return_value="(no prior memory yet)")
    act_result = MagicMock()
    act_result.success = act_success
    agent.act = AsyncMock(return_value=act_result)
    return agent


def _make_provider(decision: dict | None = None, error: Exception | None = None) -> MagicMock:
    p = MagicMock()
    p.name = "test"
    p.model_string = "test/model"
    if error is not None:
        p.decide = AsyncMock(side_effect=error)
    else:
        p.decide = AsyncMock(return_value=decision or {"action": "wait", "params": {}})
    return p


def test_one_decision_executes_action() -> None:
    mod = _import_or_skip()
    # State must contain the field that the LLM picks — otherwise the
    # S160 off-list filter drops it (this is the intended behaviour).
    agent = _make_agent(_make_state(field_ids=[("f1", 1)]))
    provider = _make_provider(
        {"action": "place_cells", "params": {"field_id": "f1", "preset": "block"}}
    )
    callback_calls: list[tuple] = []

    def on_decision(action: str, params: dict, elapsed: float, success: bool) -> None:
        callback_calls.append((action, params, success))

    asyncio.run(mod._one_decision(agent, provider, on_decision))
    agent.act.assert_awaited_once_with("place_cells", field_id="f1", preset="block")
    assert callback_calls == [("place_cells", {"field_id": "f1", "preset": "block"}, True)]


def test_one_decision_wait_skips_act() -> None:
    mod = _import_or_skip()
    agent = _make_agent()
    provider = _make_provider({"action": "wait", "params": {}})
    callback_calls: list[tuple] = []

    def on_decision(action: str, params: dict, elapsed: float, success: bool) -> None:
        callback_calls.append((action, success))

    asyncio.run(mod._one_decision(agent, provider, on_decision))
    agent.act.assert_not_awaited()
    assert callback_calls == [("wait", True)]


def test_one_decision_provider_error_keeps_pet_alive() -> None:
    """Provider error must NOT raise out of _one_decision (Pet must stay alive)."""
    mod = _import_or_skip()
    from cosmergon_pet.llm import LLMProviderError

    agent = _make_agent()
    provider = _make_provider(error=LLMProviderError("boom"))
    callback_calls: list[tuple] = []

    def on_decision(action: str, params: dict, elapsed: float, success: bool) -> None:
        callback_calls.append((action, success))

    # Must not raise
    asyncio.run(mod._one_decision(agent, provider, on_decision))
    agent.act.assert_not_awaited()
    assert callback_calls == [("(provider_error)", False)]


def test_one_decision_act_failure_logged_no_raise() -> None:
    """If agent.act raises (e.g. backend 4xx), loop logs but does not crash."""
    mod = _import_or_skip()
    # Field "x" tier=2 → evolve is in choices, so the LLM action is allowed
    # to reach agent.act — which then explodes (simulating backend 4xx).
    agent = _make_agent(_make_state(field_ids=[("x", 2)]))
    agent.act = AsyncMock(side_effect=RuntimeError("backend 400"))
    provider = _make_provider({"action": "evolve", "params": {"field_id": "x"}})
    callback_calls: list[tuple] = []

    def on_decision(action: str, params: dict, elapsed: float, success: bool) -> None:
        callback_calls.append((action, success))

    asyncio.run(mod._one_decision(agent, provider, on_decision))
    assert callback_calls == [("evolve", False)]


def test_format_world_handles_missing_state() -> None:
    mod = _import_or_skip()
    out = mod._format_world(None)
    assert "no state" in out.lower()


def test_format_world_renders_fields() -> None:
    """World-block contains energy + every field id + tier annotation."""
    mod = _import_or_skip()
    state = _make_state(
        energy=1234,
        field_ids=[("field-1", 2), ("field-2", 1)],
    )
    out = mod._format_world(state)
    assert "1234" in out
    assert "field-1" in out
    assert "field-2" in out
    # New rendering: evolve rows tag tier as "(current tier=N)"
    assert "tier=2" in out


def test_format_world_no_fields_only_wait() -> None:
    """0 Fields, 0 Cubes → only `wait` is offered."""
    mod = _import_or_skip()
    out = mod._format_world(_make_state(field_ids=[], cube_ids=[]))
    assert "wait" in out
    # No place_cells/evolve/create_field rows when there's nothing to act on
    assert "place_cells" not in out
    assert "evolve " not in out  # space avoids matching "evolve" inside other text
    assert "create_field" not in out


def test_format_world_no_create_field_when_universe_empty() -> None:
    """No cubes anywhere → create_field must NOT appear."""
    mod = _import_or_skip()
    out = mod._format_world(_make_state(field_ids=[("f1", 1)], cube_ids=[], universe_cube_ids=[]))
    assert "create_field" not in out


def test_format_world_lists_create_field_for_universe_cubes() -> None:
    """S161: every universe cube is fair game for create_field, not just owned ones.
    Backend permits any agent to add a field to any cube — the cube_ids come
    from state.universe_cubes (real backend UUIDs, no hallucination risk).
    """
    mod = _import_or_skip()
    out = mod._format_world(
        _make_state(
            field_ids=[],
            cube_ids=[],  # newcomer with no own cubes
            universe_cube_ids=["foreign-A", "foreign-B"],
        )
    )
    assert "create_field" in out
    assert "foreign-A" in out
    assert "foreign-B" in out


def test_format_world_create_field_when_only_own_cubes_present() -> None:
    """Owned cubes (no separate universe_cube_ids given → mirrors cube_ids).
    create_field rows with their real cube_ids appear.
    """
    mod = _import_or_skip()
    out = mod._format_world(_make_state(field_ids=[], cube_ids=["cube-A", "cube-B"]))
    assert "create_field" in out
    assert "cube-A" in out
    assert "cube-B" in out


def test_format_world_evolve_only_for_tier_lt_5() -> None:
    """evolve is offered for tiers 1..4. T5 is max → not eligible."""
    mod = _import_or_skip()
    out = mod._format_world(_make_state(field_ids=[("low-t", 2), ("max-t", 5)]))
    # T2 field eligible
    assert "evolve" in out
    # ...but the T5 field's id must not appear in an evolve row
    evolve_lines = [line for line in out.splitlines() if "evolve" in line]
    assert any("low-t" in line for line in evolve_lines)
    assert not any("max-t" in line for line in evolve_lines)


def test_one_decision_drops_off_list_uuid() -> None:
    """LLM hallucinates a field_id not in the offered list → dropped locally."""
    mod = _import_or_skip()
    agent = _make_agent(_make_state(field_ids=[("real-id", 1)]))
    # LLM "invents" a UUID instead of copying "real-id"
    provider = _make_provider(
        {"action": "place_cells", "params": {"field_id": "12345678-fake", "preset": "block"}}
    )
    callback_calls: list[tuple] = []

    def on_decision(action: str, params: dict, elapsed: float, success: bool) -> None:
        callback_calls.append((action, success))

    asyncio.run(mod._one_decision(agent, provider, on_decision))
    agent.act.assert_not_awaited()
    assert callback_calls == [("(off_list)", False)]


def test_safe_memory_tolerates_missing_method() -> None:
    """Older SDKs without fetch_memory_prompt return placeholder, no crash."""
    mod = _import_or_skip()
    agent = MagicMock(spec=[])  # no fetch_memory_prompt
    out = asyncio.run(mod._safe_memory(agent))
    assert "unavailable" in out.lower() or "old" in out.lower()


def test_safe_memory_tolerates_fetch_exception() -> None:
    mod = _import_or_skip()
    agent = MagicMock()
    agent.fetch_memory_prompt = AsyncMock(side_effect=RuntimeError("network down"))
    out = asyncio.run(mod._safe_memory(agent))
    assert "failed" in out.lower()


def test_disallowed_action_dropped_not_executed() -> None:
    """S157 security panel K1: action outside VALID_ACTIONS must be dropped
    before agent.act() is called — defense-in-depth against compromised LLM.
    """
    mod = _import_or_skip()
    agent = _make_agent()
    provider = _make_provider({"action": "delete_account", "params": {}})
    callback_calls: list[tuple] = []

    def on_decision(action: str, params: dict, elapsed: float, success: bool) -> None:
        callback_calls.append((action, success))

    asyncio.run(mod._one_decision(agent, provider, on_decision))
    agent.act.assert_not_awaited()
    assert callback_calls == [("(disallowed)", False)]


def test_valid_actions_set_unchanged() -> None:
    """The static allowlist (defense-in-depth) must keep covering the actions
    we route through Cosmergon. Since S160 the actions are no longer named
    in the SYSTEM_PROMPT — they are rendered dynamically in `_format_world`'s
    "Available actions" list per state — but the allowlist still gates them.
    """
    mod = _import_or_skip()
    expected = {
        "place_cells",
        "evolve",
        "create_field",
        "transfer_energy",
        "market_list",
        "market_buy",
        "wait",
    }
    assert mod.VALID_ACTIONS == expected


def test_redact_params_strips_sensitive_keys() -> None:
    """S157 security panel E1: transfer params must not appear verbatim in logs."""
    mod = _import_or_skip()
    redacted = mod._redact_params({"to_player_id": "abc-uuid", "amount": 1000, "field_id": "f1"})
    assert redacted["to_player_id"] == "<redacted>"
    assert redacted["amount"] == "<redacted>"
    assert redacted["field_id"] == "f1"  # not sensitive


def test_redact_params_handles_empty() -> None:
    mod = _import_or_skip()
    assert mod._redact_params({}) == {}


def test_build_system_prompt_uses_persona_and_name() -> None:
    """Persona-aware prompt mirrors the NPC pattern: name + persona-tone +
    preferred action sequence are all in the system prompt. Without these,
    qwen2.5:7b chose 100% wait while NPCs chose place_cells 67% of the time.
    """
    mod = _import_or_skip()
    prompt = mod._build_system_prompt("scientist", "Comet-hand")
    assert "Comet-hand" in prompt
    assert "scientist-persona" in prompt
    assert "methodical and curious" in prompt
    assert "(1) place_cells" in prompt
    assert "(4) wait" in prompt


def test_build_system_prompt_unknown_persona_falls_back_to_scientist() -> None:
    """Unknown / empty persona must not crash — defaults to scientist
    so the Pet always has a guidance block."""
    mod = _import_or_skip()
    prompt_unknown = mod._build_system_prompt("hermit", "X")
    assert "methodical and curious" in prompt_unknown  # scientist tone
    prompt_empty = mod._build_system_prompt("", "")
    assert "an autonomous agent" in prompt_empty
    assert "scientist-persona" in prompt_empty


def test_build_system_prompt_warrior_has_warrior_tone() -> None:
    """Each persona has a distinct tone block. Sanity-check warrior is
    not just a copy of scientist."""
    mod = _import_or_skip()
    sci = mod._build_system_prompt("scientist", "S")
    war = mod._build_system_prompt("warrior", "W")
    assert "methodical" in sci and "methodical" not in war
    assert "aggressive" in war and "aggressive" not in sci


def test_one_decision_passes_persona_aware_prompt_to_provider() -> None:
    """The system prompt the provider sees must reflect the agent's persona,
    not a generic one — this is what made NPCs act and the Pet wait.
    """
    mod = _import_or_skip()
    state = _make_state(field_ids=[("field-A", 1)])
    state.persona_type = "warrior"
    state.agent_name = "Comet-hand"
    agent = _make_agent(state=state)
    provider = _make_provider({"action": "wait", "params": {}})
    asyncio.run(mod._one_decision(agent, provider, None))
    call_args = provider.decide.await_args
    system_prompt_arg = (
        call_args.args[0] if call_args.args else call_args.kwargs.get("system_prompt")
    )
    assert "Comet-hand" in system_prompt_arg
    assert "warrior-persona" in system_prompt_arg


def test_maybe_dump_prompt_off_by_default(monkeypatch, tmp_path) -> None:
    """Without env var: no file I/O. Diagnostic must be opt-in only.

    Sanity-checks that loading Pet in production (env var unset) does not
    create dump artefacts.
    """
    mod = _import_or_skip()
    monkeypatch.delenv("COSMERGON_PET_PROMPT_DUMP_PATH", raising=False)
    state = _make_state()
    state.persona_type = "scientist"
    state.agent_name = "T"
    agent = _make_agent(state=state)
    mod._maybe_dump_prompt(agent, "sys", "mem", "world", {"k": "v"})
    assert list(tmp_path.iterdir()) == []  # nothing created


def test_maybe_dump_prompt_writes_jsonl_when_env_set(monkeypatch, tmp_path) -> None:
    """With env var set: one JSON line appended per call, with all 6 keys.

    Verifies the on-the-wire shape of the diagnostic file so downstream
    inspection scripts (`jq` / NPC-prompt diff) can rely on it.
    """
    mod = _import_or_skip()
    dump_file = tmp_path / "subdir" / "dump.jsonl"
    monkeypatch.setenv("COSMERGON_PET_PROMPT_DUMP_PATH", str(dump_file))
    state = _make_state()
    state.persona_type = "warrior"
    state.agent_name = "Comet-hand"
    state.agent_id = "abc-123"
    agent = _make_agent(state=state)

    mod._maybe_dump_prompt(
        agent,
        system_prompt="you are warrior",
        memory="mem-block",
        world="world-block",
        schema={"oneOf": [{"const": {"action": "wait"}}]},
    )

    assert dump_file.exists()
    lines = dump_file.read_text().splitlines()
    assert len(lines) == 1
    import json as _json

    entry = _json.loads(lines[0])
    assert set(entry.keys()) == {
        "timestamp",
        "agent_id",
        "system_prompt",
        "memory",
        "world",
        "schema",
    }
    assert entry["agent_id"] == "abc-123"
    assert entry["system_prompt"] == "you are warrior"
    assert entry["schema"] == {"oneOf": [{"const": {"action": "wait"}}]}


def test_maybe_dump_prompt_swallows_io_error(monkeypatch, tmp_path) -> None:
    """A broken dump path must not crash the decision loop.

    Pet must survive even when the diagnostic feature is misconfigured.
    """
    mod = _import_or_skip()
    # Path under a non-writable parent — make parent a file so mkdir fails
    parent = tmp_path / "block"
    parent.write_text("file-not-dir")
    monkeypatch.setenv("COSMERGON_PET_PROMPT_DUMP_PATH", str(parent / "x" / "dump.jsonl"))
    state = _make_state()
    agent = _make_agent(state=state)
    # Should not raise
    mod._maybe_dump_prompt(agent, "sys", "mem", "world", {})


# === S162 force-explore: streak counter + override ===========================


def test_force_explore_threshold_default_disabled(monkeypatch) -> None:
    """No env → 0 (disabled)."""
    mod = _import_or_skip()
    monkeypatch.delenv("PET_FORCE_EXPLORE_AFTER_N", raising=False)
    assert mod._force_explore_threshold() == 0


def test_force_explore_threshold_below_2_disabled(monkeypatch) -> None:
    """N=1 makes no sense (1× = baseline) → treated as disabled."""
    mod = _import_or_skip()
    monkeypatch.setenv("PET_FORCE_EXPLORE_AFTER_N", "1")
    assert mod._force_explore_threshold() == 0


def test_force_explore_threshold_invalid_disabled(monkeypatch) -> None:
    """Non-int env → 0."""
    mod = _import_or_skip()
    monkeypatch.setenv("PET_FORCE_EXPLORE_AFTER_N", "garbage")
    assert mod._force_explore_threshold() == 0


def test_force_explore_threshold_valid(monkeypatch) -> None:
    mod = _import_or_skip()
    monkeypatch.setenv("PET_FORCE_EXPLORE_AFTER_N", "5")
    assert mod._force_explore_threshold() == 5


def test_pick_explore_choice_prefers_market_buy_over_evolve() -> None:
    mod = _import_or_skip()
    choices = [
        {"action": "place_cells", "params": {"field_id": "f1", "preset": "block"}},
        {"action": "evolve", "params": {"field_id": "f1"}},
        {"action": "market_buy", "params": {"listing_id": "L1"}},
        {"action": "wait", "params": {}},
    ]
    pick = mod._pick_explore_choice(choices, avoid_action="place_cells")
    assert pick is not None
    assert pick["action"] == "market_buy"


def test_pick_explore_choice_excludes_avoid_action() -> None:
    mod = _import_or_skip()
    choices = [
        {"action": "place_cells", "params": {"field_id": "f1"}},
        {"action": "evolve", "params": {"field_id": "f1"}},
        {"action": "wait", "params": {}},
    ]
    pick = mod._pick_explore_choice(choices, avoid_action="place_cells")
    assert pick is not None
    assert pick["action"] == "evolve"


def test_pick_explore_choice_returns_none_when_only_avoid_and_wait() -> None:
    mod = _import_or_skip()
    choices = [
        {"action": "place_cells", "params": {"field_id": "f1"}},
        {"action": "wait", "params": {}},
    ]
    pick = mod._pick_explore_choice(choices, avoid_action="place_cells")
    assert pick is None


def test_one_decision_force_explore_overrides_after_threshold(monkeypatch) -> None:
    """Streak == threshold and same action repeats → force-override fires."""
    mod = _import_or_skip()
    monkeypatch.setenv("PET_FORCE_EXPLORE_AFTER_N", "3")

    # State must include both an own field (place_cells) and an own cube
    # with a buyable market listing for the override path to find an
    # alternative. We set up universe_cubes (create_field) as the fallback.
    state = _make_state(field_ids=[("f1", 1)], universe_cube_ids=["c1"])
    agent = _make_agent(state=state)
    provider = _make_provider(
        {"action": "place_cells", "params": {"field_id": "f1", "preset": "block"}}
    )
    callback_calls: list[tuple] = []

    def on_decision(action: str, params: dict, elapsed: float, success: bool) -> None:
        callback_calls.append((action, params, success))

    streak = {"last_action": "place_cells", "count": 2}  # at threshold-1 already
    asyncio.run(mod._one_decision(agent, provider, on_decision, streak_state=streak))

    # The forced override picked from priority order
    # (market_buy > market_list > evolve > create_field). State has tier=1
    # field → evolve is offered AND beats create_field by priority.
    assert len(callback_calls) == 1
    action, _, _ = callback_calls[0]
    assert action != "place_cells"
    assert action == "evolve"
    # Streak resets to 1 (the just-executed forced action) on success
    assert streak["last_action"] == "evolve"
    assert streak["count"] == 1


def test_one_decision_no_force_explore_when_disabled(monkeypatch) -> None:
    """Default (env unset) → no override even with high streak."""
    mod = _import_or_skip()
    monkeypatch.delenv("PET_FORCE_EXPLORE_AFTER_N", raising=False)

    state = _make_state(field_ids=[("f1", 1)], universe_cube_ids=["c1"])
    agent = _make_agent(state=state)
    provider = _make_provider(
        {"action": "place_cells", "params": {"field_id": "f1", "preset": "block"}}
    )
    callback_calls: list[tuple] = []

    def on_decision(action: str, params: dict, elapsed: float, success: bool) -> None:
        callback_calls.append((action, params, success))

    streak = {"last_action": "place_cells", "count": 99}  # huge streak
    asyncio.run(mod._one_decision(agent, provider, on_decision, streak_state=streak))

    # Disabled → place_cells passes through, streak increments normally
    action, _, _ = callback_calls[0]
    assert action == "place_cells"
    assert streak["count"] == 100


def test_one_decision_streak_increments_on_repeat(monkeypatch) -> None:
    """Same action twice in a row → streak.count goes 1 → 2 (no override below threshold)."""
    mod = _import_or_skip()
    monkeypatch.setenv("PET_FORCE_EXPLORE_AFTER_N", "5")

    state = _make_state(field_ids=[("f1", 1)])
    agent = _make_agent(state=state)
    provider = _make_provider(
        {"action": "place_cells", "params": {"field_id": "f1", "preset": "block"}}
    )

    streak = {"last_action": None, "count": 0}
    asyncio.run(mod._one_decision(agent, provider, None, streak_state=streak))
    assert streak == {"last_action": "place_cells", "count": 1}
    asyncio.run(mod._one_decision(agent, provider, None, streak_state=streak))
    assert streak == {"last_action": "place_cells", "count": 2}


def test_one_decision_streak_resets_on_action_change(monkeypatch) -> None:
    """Different action → streak resets to count=1 with new last_action."""
    mod = _import_or_skip()
    monkeypatch.setenv("PET_FORCE_EXPLORE_AFTER_N", "5")

    state = _make_state(field_ids=[("f1", 2)])
    agent = _make_agent(state=state)
    # First place_cells, then evolve
    provider1 = _make_provider(
        {"action": "place_cells", "params": {"field_id": "f1", "preset": "block"}}
    )
    provider2 = _make_provider({"action": "evolve", "params": {"field_id": "f1"}})

    streak = {"last_action": "place_cells", "count": 3}
    asyncio.run(mod._one_decision(agent, provider1, None, streak_state=streak))
    assert streak == {"last_action": "place_cells", "count": 4}

    asyncio.run(mod._one_decision(agent, provider2, None, streak_state=streak))
    assert streak == {"last_action": "evolve", "count": 1}


def test_one_decision_streak_resets_on_wait(monkeypatch) -> None:
    mod = _import_or_skip()
    monkeypatch.setenv("PET_FORCE_EXPLORE_AFTER_N", "5")

    state = _make_state()
    agent = _make_agent(state=state)
    provider = _make_provider({"action": "wait", "params": {}})

    streak = {"last_action": "place_cells", "count": 4}
    asyncio.run(mod._one_decision(agent, provider, None, streak_state=streak))
    assert streak == {"last_action": None, "count": 0}


def test_one_decision_streak_resets_on_failed_action(monkeypatch) -> None:
    mod = _import_or_skip()
    monkeypatch.setenv("PET_FORCE_EXPLORE_AFTER_N", "5")

    state = _make_state(field_ids=[("f1", 1)])
    agent = _make_agent(state=state, act_success=False)
    provider = _make_provider(
        {"action": "place_cells", "params": {"field_id": "f1", "preset": "block"}}
    )

    streak = {"last_action": "place_cells", "count": 3}
    asyncio.run(mod._one_decision(agent, provider, None, streak_state=streak))
    assert streak == {"last_action": None, "count": 0}


if __name__ == "__main__":
    test_one_decision_executes_action()
    test_one_decision_wait_skips_act()
    test_one_decision_provider_error_keeps_pet_alive()
    test_one_decision_act_failure_logged_no_raise()
    test_format_world_handles_missing_state()
    test_format_world_renders_fields()
    test_safe_memory_tolerates_missing_method()
    test_safe_memory_tolerates_fetch_exception()
    print("OK")
