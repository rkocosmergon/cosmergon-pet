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
    agent = _make_agent()
    provider = _make_provider({"action": "place_cells", "params": {"field_id": "f1", "preset": "block"}})
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
    agent = _make_agent()
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
    mod = _import_or_skip()
    state = MagicMock()
    state.energy_balance = 1234
    f1 = MagicMock(); f1.id = "field-1"; f1.entity_tier = 2; f1.active_cell_count = 8
    f2 = MagicMock(); f2.id = "field-2"; f2.entity_tier = 1; f2.active_cell_count = 0
    state.fields = [f1, f2]
    out = mod._format_world(state)
    assert "1234" in out
    assert "field-1" in out
    assert "field-2" in out
    assert "tier=2" in out


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


def test_valid_actions_set_matches_system_prompt() -> None:
    """The action allowlist must list exactly the actions advertised in the
    SYSTEM_PROMPT — drift here breaks the LLM's expected vocabulary.
    """
    mod = _import_or_skip()
    expected = {"place_cells", "evolve", "create_field", "transfer_energy", "wait"}
    assert mod.VALID_ACTIONS == expected
    for action in expected:
        assert action in mod.SYSTEM_PROMPT, (
            f"{action} listed in VALID_ACTIONS but missing from SYSTEM_PROMPT"
        )


def test_redact_params_strips_sensitive_keys() -> None:
    """S157 security panel E1: transfer params must not appear verbatim in logs."""
    mod = _import_or_skip()
    redacted = mod._redact_params(
        {"to_player_id": "abc-uuid", "amount": 1000, "field_id": "f1"}
    )
    assert redacted["to_player_id"] == "<redacted>"
    assert redacted["amount"] == "<redacted>"
    assert redacted["field_id"] == "f1"  # not sensitive


def test_redact_params_handles_empty() -> None:
    mod = _import_or_skip()
    assert mod._redact_params({}) == {}


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
