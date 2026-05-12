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


_TIER_REQUIRED_TYPE_DEFAULT: dict[int, str] = {
    1: "oscillator",  # T1 → T2 needs oscillator
    2: "spaceship",  # T2 → T3 needs spaceship
    3: "gun",  # T3 → T4 needs gun
    4: "breeder",  # T4 → T5 needs breeder
    5: "breeder",  # T5 max — evolve blocked anyway by tier>=5 short-circuit
}


def _make_state(
    *,
    energy: float = 1_000_000.0,
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

    Defaults for evolve-eligibility are deliberately *generous*: every
    field is reife-saturated (100 000) and gets the entity_type the
    backend requires for `next_tier=tier+1`. Plus energy=1 000 000 covers
    every EVOLUTION_ENERGY_COST. Tests that need to verify the
    can-evolve filter (S164: reife / entity_type / energy gates)
    override these per-field via `_set_field` or use the
    `_make_field`/`_state_with_fields` builders below.
    """
    state = MagicMock()
    state.energy = energy
    state.fields = []
    for fid, tier in field_ids or []:
        f = MagicMock()
        f.id = fid
        f.entity_tier = tier
        f.active_cell_count = 3
        f.reife_score = 100_000
        f.entity_type = _TIER_REQUIRED_TYPE_DEFAULT.get(tier, "oscillator")
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
        energy=1_000_000,  # cover EVOLUTION_ENERGY_COST gate (S164)
        field_ids=[("field-1", 2), ("field-2", 1)],
    )
    out = mod._format_world(state)
    assert "1000000" in out or "1,000,000" in out  # energy printed
    assert "field-1" in out
    assert "field-2" in out
    # evolve rows tag tier transition as "T{tier}->T{next_tier}" (S164)
    assert "T2->T3" in out  # field-1 evolve eligibility
    assert "T1->T2" in out  # field-2 evolve eligibility


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


# S164 — H_NEXT verification: `_build_action_choices` must mirror backend
# `_handle_evolve` (reife/entity_type/balance gates). Pre-S164 only the
# tier gate was checked; backend rejected 30/30 evolve calls in 3h with
# "Entity not mature enough" or "Pattern type does not match target tier".


def test_evolve_filtered_by_reife_threshold() -> None:
    """Field with reife_score below REIFE_THRESHOLDS[next_tier] → no evolve row.

    REIFE_THRESHOLDS[3]=500. T2 field with reife=100 must not be offered.
    """
    mod = _import_or_skip()
    state = _make_state(field_ids=[("not-mature", 2)])
    state.fields[0].reife_score = 100  # below T3 threshold 500
    out = mod._format_world(state)
    evolve_lines = [line for line in out.splitlines() if "evolve" in line]
    assert not any("not-mature" in line for line in evolve_lines)


def test_evolve_filtered_by_entity_type_mismatch() -> None:
    """T1 still_life cannot evolve to T2 (T2 requires oscillator) → no evolve row."""
    mod = _import_or_skip()
    state = _make_state(field_ids=[("wrong-type", 1)])
    state.fields[0].entity_type = "still_life"  # T2 requires oscillator
    state.fields[0].reife_score = 1_000  # safely over T2 threshold
    out = mod._format_world(state)
    evolve_lines = [line for line in out.splitlines() if "evolve" in line]
    assert not any("wrong-type" in line for line in evolve_lines)


def test_evolve_filtered_by_insufficient_balance() -> None:
    """Balance below EVOLUTION_ENERGY_COST[tier] → no evolve row.

    EVOLUTION_ENERGY_COST[2]=5000. T2 field with energy=100 must not be offered
    (cost is paid at tier=current, not next_tier).
    """
    mod = _import_or_skip()
    state = _make_state(energy=100, field_ids=[("poor", 2)])
    out = mod._format_world(state)
    evolve_lines = [line for line in out.splitlines() if "evolve" in line]
    assert not any("poor" in line for line in evolve_lines)


def test_evolve_offered_when_all_filters_pass() -> None:
    """Defense in depth: state with full eligibility produces an evolve row."""
    mod = _import_or_skip()
    state = _make_state(field_ids=[("eligible", 2)])
    # _make_state defaults already give reife=100 000, type=spaceship,
    # energy=1 000 000 — all gates pass.
    out = mod._format_world(state)
    evolve_lines = [line for line in out.splitlines() if "evolve" in line]
    assert any("eligible" in line for line in evolve_lines)


# S165 — propose_contract surfacing. Added to VALID_ACTIONS + persona
# sequences with conditional path. Choices are gated on:
#   - state.world_briefing.contract_targets (backend ≥ S165)
#   - energy >= _PROPOSE_CONTRACT_MIN_BALANCE (5 000 E)
# Free-tier types only: non_aggression, trade_agreement.


def _add_contract_targets(
    state: MagicMock,
    targets: list[tuple[str, str, str | None]],
) -> None:
    """Attach a contract_targets list to state.world_briefing.

    Each target is (player_id, username, persona_or_None).
    """
    target_objs = []
    for tid, name, persona in targets:
        t = MagicMock()
        t.player_id = tid
        t.username = name
        t.persona = persona
        target_objs.append(t)
    state.world_briefing.contract_targets = target_objs


def test_propose_contract_offered_when_balance_and_targets() -> None:
    """Balance >= 5000 + at least one target → one branch per (target × free-type)."""
    mod = _import_or_skip()
    state = _make_state(energy=10_000, field_ids=[("f1", 1)])
    _add_contract_targets(state, [("p1", "Aldous", "scientist")])

    choices = mod._build_action_choices(state)
    pc = [c for c in choices if c["action"] == "propose_contract"]
    # 2 free-tier types × 1 target = 2 branches
    assert len(pc) == 2
    types = {c["params"]["contract_type"] for c in pc}
    assert types == {"non_aggression", "trade_agreement"}
    # Every branch has the target id pinned + escrow=0 + terms-template
    for c in pc:
        assert c["params"]["to_player_id"] == "p1"
        assert c["params"]["escrow_amount"] == 0
        assert c["params"]["terms"] == {"duration_ticks": 100}
        assert "Aldous" in c["label"]


def test_propose_contract_skipped_below_min_balance() -> None:
    """Balance below 5 000 E (sustain mode) → no propose_contract row even with targets."""
    mod = _import_or_skip()
    state = _make_state(energy=1_000, field_ids=[("f1", 1)])
    _add_contract_targets(state, [("p1", "Aldous", "scientist")])

    choices = mod._build_action_choices(state)
    pc = [c for c in choices if c["action"] == "propose_contract"]
    assert pc == []


def test_propose_contract_skipped_when_no_targets() -> None:
    """Empty contract_targets list (older backend or quiet world) → no row."""
    mod = _import_or_skip()
    state = _make_state(energy=100_000, field_ids=[("f1", 1)])
    state.world_briefing.contract_targets = []

    choices = mod._build_action_choices(state)
    pc = [c for c in choices if c["action"] == "propose_contract"]
    assert pc == []


def test_propose_contract_capped_at_max_targets() -> None:
    """More than _PROPOSE_CONTRACT_MAX_TARGETS counterparts → capped, schema stays small."""
    mod = _import_or_skip()
    state = _make_state(energy=100_000, field_ids=[("f1", 1)])
    many = [(f"p{i}", f"Agent{i}", "trader") for i in range(20)]
    _add_contract_targets(state, many)

    choices = mod._build_action_choices(state)
    pc = [c for c in choices if c["action"] == "propose_contract"]
    # cap × 2 free-tier types
    assert len(pc) == mod._PROPOSE_CONTRACT_MAX_TARGETS * 2


def test_propose_contract_in_choices_validates_match() -> None:
    """`_is_action_in_choices` must accept the exact (action, params)
    triple from a propose_contract branch — otherwise the schema-mode
    decision would be dropped as off-list.
    """
    mod = _import_or_skip()
    state = _make_state(energy=10_000, field_ids=[("f1", 1)])
    _add_contract_targets(state, [("p1", "Aldous", "scientist")])

    choices = mod._build_action_choices(state)
    pc = [c for c in choices if c["action"] == "propose_contract"]
    assert pc, "guard: propose_contract must be offered for this test"
    sample = pc[0]
    assert mod._is_action_in_choices(sample["action"], sample["params"], choices)


def test_personas_mention_propose_contract() -> None:
    """Each of the 6 personas must mention propose_contract conditionally
    in its sequence — this is the L1-pattern extension that lets the
    LLM ever pick the action when offered.
    """
    mod = _import_or_skip()
    for persona in ("scientist", "warrior", "diplomat", "farmer", "expansionist", "trader"):
        prompt = mod._build_system_prompt(persona, f"{persona}-bot")
        assert "propose_contract" in prompt, (
            f"{persona} sequence missing propose_contract conditional"
        )


def test_diplomat_propose_contract_priority_over_market() -> None:
    """Diplomat is the persona where propose_contract is the prime move
    once balance allows. The conditional MUST appear in the prompt
    BEFORE the market_buy line — otherwise the LLM keeps falling
    through to market actions first.
    """
    mod = _import_or_skip()
    prompt = mod._build_system_prompt("diplomat", "D")
    pc_idx = prompt.find("propose_contract")
    mb_idx = prompt.find("market_buy")
    assert pc_idx > 0 and mb_idx > 0
    assert pc_idx < mb_idx, "diplomat must list propose_contract before market_buy"


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
        "create_cube",
        "transfer_energy",
        "market_list",
        "market_buy",
        "propose_contract",
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
    # S162 L1: scientist sequence is now conditional ("WHEN to act / IF / ELSE").
    # market_buy + market_list + evolve sind alle conditional erwähnt.
    assert "WHEN to act" in prompt
    assert "evolve" in prompt
    assert "place_cells" in prompt
    assert "market_buy" in prompt
    assert "market_list" in prompt
    assert "ELSE" in prompt


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


def test_build_system_prompt_examples_are_persona_specific() -> None:
    """S162 P1-FAIL-Diagnose: hard-coded examples zeigten NUR
    place_cells/evolve/wait — bei 3B-LLM überstimmten sie die
    abstrakte conditional sequence (Comet-hand 99% place_cells trotz
    scientist-Pfad-5 für create_field). Examples sind jetzt persona-
    spezifisch und decken die Top-Pfade jeder Persona ab.
    """
    mod = _import_or_skip()
    sci = mod._build_system_prompt("scientist", "S")
    war = mod._build_system_prompt("warrior", "W")
    trd = mod._build_system_prompt("trader", "T")
    exp = mod._build_system_prompt("expansionist", "E")
    # scientist examples must demonstrate create_field (Pfad 5) — the
    # bug we fixed: previously no example mentioned create_field at all.
    assert "create_field" in sci
    # trader examples must demonstrate market_buy (Pfad 1) and market_list (Pfad 2)
    assert "market_buy" in trd
    assert "market_list" in trd
    # expansionist examples must demonstrate create_field (Pfad 1, flagship)
    assert "create_field" in exp and "flagship" in exp
    # warrior examples must demonstrate place_cells with low-cell-count gap
    assert "place_cells" in war
    # All persona examples include the new Pfad-N-Verweis
    assert "Pfad" in sci
    assert "Pfad" in war


def test_build_system_prompt_unknown_persona_uses_fallback_examples() -> None:
    """Unknown persona falls back to scientist (not generic) — scientist
    examples themselves serve as the fallback because the dict-lookup
    falls back to scientist guidance entirely.
    """
    mod = _import_or_skip()
    pr = mod._build_system_prompt("hermit", "X")
    # Scientist's create_field example must appear (= scientist fallback active)
    assert "create_field" in pr


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
        "phase",
        "timestamp",
        "agent_id",
        "system_prompt",
        "memory",
        "world",
        "schema",
    }
    assert entry["phase"] == "input"
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
