"""The tree loop must decide without an external state poller (S306).

This is the failure reproduced in production: a container ran
``tree_decision_loop`` for minutes, logged nothing beyond "started", and
executed **zero** actions — because nothing kept ``agent.state`` fresh and the
loop skipped every round at DEBUG level. It was invisible in the log and only
showed up in the server's records.
"""

from __future__ import annotations

import pytest

from cosmergon_pet.tree_loop import _one_tree_decision


class _Decider:
    name = "tree"

    def __init__(self) -> None:
        self.seen_state = None

    async def decide(self, state, blocked=frozenset()):
        self.seen_state = state
        return "wait", {}


class _Result:
    success = True


class _Agent:
    """Agent whose state only becomes available via ``refresh_state``."""

    def __init__(self, fetched=None) -> None:
        self.state = None
        self._fetched = fetched
        self.refresh_calls = 0
        self.actions: list[str] = []

    async def refresh_state(self):
        self.refresh_calls += 1
        self.state = self._fetched
        return self._fetched

    async def act(self, action, **params):
        self.actions.append(action)
        return _Result()


@pytest.mark.asyncio
async def test_decides_although_nobody_polls_the_state():
    """Against the pre-S306 code this fails: the round was skipped in silence."""
    agent = _Agent(fetched="welt")
    decider = _Decider()

    await _one_tree_decision(agent, decider, None)

    assert agent.refresh_calls == 1, "loop did not obtain the state itself"
    assert decider.seen_state == "welt", "decider was never asked"


@pytest.mark.asyncio
async def test_without_any_state_the_decider_is_not_asked():
    """No state means nothing to decide — but it must not raise either."""
    agent = _Agent(fetched=None)
    decider = _Decider()

    await _one_tree_decision(agent, decider, None)

    assert decider.seen_state is None
    assert agent.actions == []
