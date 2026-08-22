"""Shared state access for the decision loops — fetch what you need, say when you can't.

WHY THIS MODULE EXISTS
----------------------
Both decision loops (``tree_loop``, ``llm_decider``) *read* ``agent.state`` but
neither *obtains* it. Keeping it fresh was an unwritten duty of whoever started
the loop — inside the Pet that is ``face.py``'s polling task, which mirrors each
``/state`` response into the SDK's private slot::

    agent._state = state  # intentional cross-module sync

That line has been in ``face.py`` since 2026-05-04, added after the LLM decider
was found running on an empty ``GameState``: ``_build_action_choices`` collapsed
to the ``wait`` line only, and the Pet looked healthy while deciding nothing.

The flaw was never the missing poll — it was that a loop which *cannot work*
without the state also *does not ask* for it, and stays quiet when it is absent:

* ``tree_loop`` logged ``debug("agent.state still None, skip")`` and returned,
  so the loop reported "started" and then skipped every round in silence.
* ``llm_decider`` passed ``None`` straight into ``_build_action_choices``,
  degrading to ``wait`` without any signal at all.

Running either loop outside the Pet reproduces this immediately (S306: a
container ran the tree loop for minutes, logged nothing but "started", and
executed zero actions — visible only in the server's records, not in the log).

WHAT THIS MODULE CHANGES
------------------------
The loops now ask for what they need instead of assuming someone else supplied
it, and a persistent absence becomes audible rather than silent. Inside the Pet
nothing changes: ``agent.state`` is already populated, so no extra request is
made — the fetch is a fallback, not a second poller.
"""

from __future__ import annotations

import logging
from typing import Any

__all__ = ["StateSource"]

logger = logging.getLogger(__name__)

DEFAULT_LOUD_AFTER = 3
"""Consecutive empty rounds before warning.

Not zero: a freshly started agent legitimately has no state for a round or two,
and a warning on the first tick would train the reader to ignore it. Not large
either — three rounds of a 60 s loop is three minutes of doing nothing, which is
already worth saying out loud.
"""


class StateSource:
    """Supplies the current ``GameState`` to a decision loop.

    Order of preference:

    1. ``agent.state`` — set by whoever polls (the Pet's display loop does).
    2. ``agent.refresh_state()`` — fetched here when nobody did.

    Keeps one counter so that a *persistent* absence is reported once at
    WARNING instead of once per round, and reports recovery too. Callers hold
    one instance per loop, mirroring how ``tree_loop`` holds its ``_Backoff``.
    """

    def __init__(self, loud_after: int = DEFAULT_LOUD_AFTER) -> None:
        self._missing_rounds = 0
        self._loud_after = loud_after

    async def current(self, agent: Any) -> Any | None:
        """Return the state, fetching it if needed — or ``None`` and say so."""
        state = getattr(agent, "state", None)
        if state is None:
            state = await self._fetch(agent)

        if state is None:
            self._missing_rounds += 1
            if self._missing_rounds == self._loud_after:
                logger.warning(
                    "no game state for %d consecutive rounds — the decider is "
                    "idling. Is the agent connected and the API key valid?",
                    self._missing_rounds,
                )
            else:
                logger.debug("no game state (round %d)", self._missing_rounds)
            return None

        if self._missing_rounds >= self._loud_after:
            logger.info("game state available again after %d rounds", self._missing_rounds)
        self._missing_rounds = 0
        return state

    @staticmethod
    async def _fetch(agent: Any) -> Any | None:
        """One ``refresh_state()`` attempt — never raises.

        Absent on very old SDKs; treated like a failed fetch rather than an
        error, so an outdated client degrades instead of crashing the loop.
        """
        refresh = getattr(agent, "refresh_state", None)
        if refresh is None:
            logger.debug("SDK has no refresh_state(); relying on external polling")
            return None
        try:
            return await refresh()
        except Exception as e:
            # Same contract as the loops: nothing here may kill the Pet.
            logger.warning("refresh_state() failed: %s", e)
            return None
