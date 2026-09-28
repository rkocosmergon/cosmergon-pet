"""No second action in the same server tick (cosmergon#392, second pass).

Measured 2026-09-28 06:45-07:45Z with Pet 0.8.8: 10.5 % of the Pet's actions still
came back 429. ``next_tick_at`` is an estimate from the mean period, and real ticks
vary by several seconds (67-74 s); 2 s of buffer did not cover it. The loops now
compare the server's tick counter — the same one the one-action-per-tick rule
counts — instead of trusting the clock alone.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from cosmergon_pet import agent_state
from cosmergon_pet.agent_state import aktueller_tick, tick_wechsel_abwarten
from cosmergon_pet.tree_loop import tree_decision_loop


class _TickAgent:
    """Agent whose server tick advances only after ``bleibt`` fetches."""

    def __init__(self, start: int = 7, bleibt: int = 3) -> None:
        self.tick = start
        self._bleibt = bleibt
        self.fetches = 0
        self.akte: list[int] = []
        self.state = SimpleNamespace(tick=start, next_tick_at=None)

    async def refresh_state(self):
        self.fetches += 1
        if self.fetches % self._bleibt == 0:
            self.tick += 1
        self.state = SimpleNamespace(tick=self.tick, next_tick_at=None)
        return self.state

    async def act(self, action, **params):
        self.akte.append(self.tick)
        return SimpleNamespace(success=True)


@pytest.fixture(autouse=True)
def _schnell(monkeypatch):
    monkeypatch.setattr(agent_state, "TICK_NACHFRAGE_S", 0.001)


@pytest.mark.asyncio
async def test_waits_until_the_tick_moves() -> None:
    agent = _TickAgent(start=7, bleibt=3)
    await tick_wechsel_abwarten(agent, 7, asyncio.Event(), hoechstens_s=5.0)
    assert agent.tick == 8
    assert agent.fetches == 3


@pytest.mark.asyncio
async def test_gives_up_after_the_bound() -> None:
    agent = _TickAgent(start=7, bleibt=10_000)
    await tick_wechsel_abwarten(agent, 7, asyncio.Event(), hoechstens_s=0.05)
    assert agent.tick == 7


@pytest.mark.asyncio
async def test_no_reference_no_wait() -> None:
    agent = _TickAgent()
    await tick_wechsel_abwarten(agent, None, asyncio.Event(), hoechstens_s=5.0)
    assert agent.fetches == 0


@pytest.mark.asyncio
async def test_current_tick_is_fresh_not_cached() -> None:
    agent = _TickAgent(start=7, bleibt=1)  # every fetch moves the tick
    agent.state = SimpleNamespace(tick=3, next_tick_at=None)  # stale cache
    assert await aktueller_tick(agent) == 8


@pytest.mark.asyncio
async def test_tree_loop_never_acts_twice_in_one_tick() -> None:
    """Wiring: the loop itself, not only the helper. Red against 0.8.8."""
    agent = _TickAgent(start=7, bleibt=4)

    class _Decider:
        name = "stub"

        async def decide(self, state, blocked=frozenset()):
            return "place_cells", {}

    stop = asyncio.Event()
    lauf = asyncio.create_task(tree_decision_loop(agent, _Decider(), interval_s=0.001, stop=stop))
    for _ in range(200):
        await asyncio.sleep(0.002)
        if len(agent.akte) >= 4:
            break
    stop.set()
    await asyncio.wait_for(lauf, timeout=2)

    assert len(agent.akte) >= 3
    assert len(agent.akte) == len(set(agent.akte)), agent.akte
