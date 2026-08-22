"""A decision loop must obtain its state — and say so when it cannot (S306).

Background: both loops read ``agent.state`` without ever fetching it. Keeping it
fresh was an unwritten duty of the caller (inside the Pet: ``face.py``'s polling
task, mirroring into the SDK's private ``_state``). Run either loop without that
caller and it skips every round in silence — "started" in the log, zero actions
in reality. See ``cosmergon_pet.agent_state`` for the full account.
"""

from __future__ import annotations

import logging

import pytest

from cosmergon_pet.agent_state import DEFAULT_LOUD_AFTER, StateSource


class _Agent:
    """Minimal stand-in: a state slot plus an optional fetch."""

    def __init__(self, state=None, fetched=None, raises: bool = False) -> None:
        self.state = state
        self._fetched = fetched
        self._raises = raises
        self.refresh_calls = 0

    async def refresh_state(self):
        self.refresh_calls += 1
        if self._raises:
            raise RuntimeError("network down")
        return self._fetched


@pytest.mark.asyncio
async def test_uses_existing_state_without_fetching():
    """Inside the Pet the state is already there — no second request."""
    agent = _Agent(state="vorhanden")

    assert await StateSource().current(agent) == "vorhanden"
    assert agent.refresh_calls == 0, "fetched although a state was present"


@pytest.mark.asyncio
async def test_fetches_when_nobody_supplied_one():
    """The core of S306: without an external poller the loop fetches itself.

    Against the pre-S306 code this fails — there the round was skipped and the
    loop idled forever.
    """
    agent = _Agent(state=None, fetched="geholt")

    assert await StateSource().current(agent) == "geholt"
    assert agent.refresh_calls == 1


@pytest.mark.asyncio
async def test_failed_fetch_yields_none_and_does_not_raise():
    """The loops' contract: nothing in here may kill the Pet."""
    agent = _Agent(state=None, raises=True)

    assert await StateSource().current(agent) is None


@pytest.mark.asyncio
async def test_old_sdk_without_refresh_degrades_quietly():
    """An SDK lacking ``refresh_state`` must degrade, not crash."""

    class _Ancient:
        state = None

    assert await StateSource().current(_Ancient()) is None


@pytest.mark.asyncio
async def test_persistent_absence_becomes_a_warning(caplog):
    """Silence was the actual defect — a lasting absence has to be audible."""
    agent = _Agent(state=None, fetched=None)
    source = StateSource()

    with caplog.at_level(logging.WARNING, logger="cosmergon_pet.agent_state"):
        for _ in range(DEFAULT_LOUD_AFTER):
            assert await source.current(agent) is None

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1, "expected exactly one warning, not one per round"
    assert "idling" in warnings[0].getMessage()


@pytest.mark.asyncio
async def test_warns_once_not_every_round(caplog):
    """A loop that shouts every 60 s trains the reader to ignore it."""
    agent = _Agent(state=None, fetched=None)
    source = StateSource()

    with caplog.at_level(logging.WARNING, logger="cosmergon_pet.agent_state"):
        for _ in range(DEFAULT_LOUD_AFTER * 3):
            await source.current(agent)

    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1


@pytest.mark.asyncio
async def test_recovery_is_reported_and_counter_resets(caplog):
    """Coming back matters as much as going away."""
    agent = _Agent(state=None, fetched=None)
    source = StateSource()
    for _ in range(DEFAULT_LOUD_AFTER):
        await source.current(agent)

    agent.state = "wieder da"
    with caplog.at_level(logging.INFO, logger="cosmergon_pet.agent_state"):
        assert await source.current(agent) == "wieder da"

    assert any("available again" in r.getMessage() for r in caplog.records)

    # Counter reset: the next gap must be allowed to warn again.
    agent.state = None
    with caplog.at_level(logging.WARNING, logger="cosmergon_pet.agent_state"):
        caplog.clear()
        for _ in range(DEFAULT_LOUD_AFTER):
            await source.current(agent)
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1


@pytest.mark.asyncio
async def test_first_empty_round_stays_quiet(caplog):
    """A freshly started agent legitimately has no state yet."""
    agent = _Agent(state=None, fetched=None)

    with caplog.at_level(logging.WARNING, logger="cosmergon_pet.agent_state"):
        await StateSource().current(agent)

    assert not [r for r in caplog.records if r.levelno == logging.WARNING]
