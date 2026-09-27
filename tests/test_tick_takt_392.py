"""The decision loops wait for the next game tick, not for a fixed 60 s (cosmergon#392).

Measured 2026-09-27: a tick lasted ~131 s, both loops fired every 60 s, and 38 % of
the Pet's actions came back 429 ("Max 1 action per tick"). The server has published
``next_tick_at`` in the state since S314; the Pet never read it.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cosmergon_pet.agent_state import TICK_PUFFER_S, sekunden_bis_zur_naechsten_runde

JETZT = 1_000_000.0


class _Agent:
    def __init__(self, next_tick_at=None, fetched_next=None) -> None:
        self.state = SimpleNamespace(next_tick_at=next_tick_at)
        self._fetched = SimpleNamespace(next_tick_at=fetched_next)
        self.refresh_calls = 0

    async def refresh_state(self):
        self.refresh_calls += 1
        return self._fetched


@pytest.mark.asyncio
async def test_waits_for_the_next_tick_when_it_is_further_than_the_interval():
    agent = _Agent(next_tick_at=JETZT + 125)
    warte = await sekunden_bis_zur_naechsten_runde(agent, 60.0, jetzt=JETZT)
    assert warte == 125 + TICK_PUFFER_S
    assert agent.refresh_calls == 0


@pytest.mark.asyncio
async def test_never_faster_than_the_own_interval():
    agent = _Agent(next_tick_at=JETZT + 5)
    assert await sekunden_bis_zur_naechsten_runde(agent, 60.0, jetzt=JETZT) == 60.0


@pytest.mark.asyncio
async def test_stale_state_is_fetched_once_more():
    """next_tick_at in the past = the state predates the last tick."""
    agent = _Agent(next_tick_at=JETZT - 10, fetched_next=JETZT + 90)
    warte = await sekunden_bis_zur_naechsten_runde(agent, 60.0, jetzt=JETZT)
    assert agent.refresh_calls == 1
    assert warte == 90 + TICK_PUFFER_S


@pytest.mark.asyncio
async def test_without_next_tick_at_the_old_interval_stays():
    agent = _Agent(next_tick_at=None, fetched_next=None)
    assert await sekunden_bis_zur_naechsten_runde(agent, 60.0, jetzt=JETZT) == 60.0


@pytest.mark.asyncio
async def test_a_failing_fetch_never_raises():
    class _Kaputt:
        state = None

        async def refresh_state(self):
            raise RuntimeError("network down")

    assert await sekunden_bis_zur_naechsten_runde(_Kaputt(), 60.0, jetzt=JETZT) == 60.0
