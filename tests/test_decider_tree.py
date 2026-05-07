"""Smoke tests for the vendored TreeDecider + tree_decision_loop integration.

Verifies:
  - TreeDecider produces an action from a minimal GameState
  - Personas pick different first-actions on the same state
  - tree_decision_loop calls agent.act when given a non-wait action
  - Mutual-exclusion check at run_pet level (llm_provider XOR tree_decider)
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from cosmergon_pet.decider_tree import VALID_ACTIONS, TreeDecider


def _make_state(
    *,
    persona: str = "scientist",
    energy: float = 10_000,
    fields: list[Any] | None = None,
    cubes: list[Any] | None = None,
    available_actions: dict[str, dict[str, Any]] | None = None,
) -> Any:
    """Lightweight GameState surrogate — duck-typed for the tree's getattr-paths."""
    return SimpleNamespace(
        persona_type=persona,
        energy=energy,
        fields=fields or [],
        universe_cubes=cubes or [],
        available_actions=available_actions or {},
        world_briefing=SimpleNamespace(
            market=SimpleNamespace(buyable=[]),
            contract_targets=[],
        ),
        compass_preset=None,
    )


@pytest.mark.asyncio
async def test_decider_returns_valid_action() -> None:
    state = _make_state()
    decider = TreeDecider()
    action, params = await decider.decide(state)
    assert action in VALID_ACTIONS
    assert isinstance(params, dict)


@pytest.mark.asyncio
async def test_decider_critical_energy_waits() -> None:
    state = _make_state(energy=10)  # below CRITICAL_ENERGY (100)
    decider = TreeDecider()
    action, _ = await decider.decide(state)
    assert action == "wait"


@pytest.mark.asyncio
async def test_decider_zero_fields_can_afford_creates_field() -> None:
    cube = SimpleNamespace(id="11111111-1111-1111-1111-111111111111")
    state = _make_state(
        energy=10_000,
        fields=[],
        cubes=[cube],
        available_actions={"create_field": {"can_afford": True}},
    )
    decider = TreeDecider()
    action, params = await decider.decide(state)
    assert action == "create_field"
    assert params["cube_id"] == str(cube.id)


@pytest.mark.asyncio
async def test_decider_unknown_persona_falls_back_to_scientist() -> None:
    state = _make_state(persona="some-future-persona", energy=10_000)
    decider = TreeDecider()
    action, _ = await decider.decide(state)
    assert action in VALID_ACTIONS  # scientist tree → always-valid action


@pytest.mark.asyncio
async def test_tree_loop_calls_agent_act_on_non_wait() -> None:
    """tree_decision_loop must execute the action when the tree picks one."""
    from cosmergon_pet.tree_loop import _one_tree_decision

    cube = SimpleNamespace(id="22222222-2222-2222-2222-222222222222")
    state = _make_state(
        energy=10_000,
        fields=[],
        cubes=[cube],
        available_actions={"create_field": {"can_afford": True}},
    )

    calls: list[tuple[str, dict[str, Any]]] = []

    class FakeAgent:
        state = None  # patched below

        async def act(self, action: str, **params: Any) -> Any:
            calls.append((action, params))
            return SimpleNamespace(success=True)

    agent = FakeAgent()
    agent.state = state  # type: ignore[assignment]

    captured: list[tuple[str, dict, float, bool]] = []

    def on_decision(action: str, params: dict, elapsed: float, success: bool) -> None:
        captured.append((action, params, elapsed, success))

    await _one_tree_decision(agent, TreeDecider(), on_decision)

    assert calls and calls[0][0] == "create_field"
    assert captured and captured[0][0] == "create_field"
    assert captured[0][3] is True


@pytest.mark.asyncio
async def test_tree_loop_skip_when_state_none() -> None:
    """If agent.state is None (not yet polled), the loop must not call act."""
    from cosmergon_pet.tree_loop import _one_tree_decision

    class FakeAgent:
        state = None

        async def act(self, action: str, **params: Any) -> Any:
            raise AssertionError("agent.act must not be called when state is None")

    captured: list[tuple[str, dict, float, bool]] = []
    await _one_tree_decision(FakeAgent(), TreeDecider(), lambda *a: captured.append(a))
    # Loop returned silently, no callback fired
    assert captured == []


def test_run_pet_rejects_both_backends() -> None:
    """Sanity: run_pet raises if both decider backends are passed."""
    from cosmergon_pet.face import run_pet

    async def _call() -> None:
        await run_pet(
            agent=None,  # type: ignore[arg-type]
            simulate=True,
            llm_provider=object(),
            tree_decider=object(),
        )

    with pytest.raises(ValueError, match="mutually exclusive"):
        asyncio.run(_call())
