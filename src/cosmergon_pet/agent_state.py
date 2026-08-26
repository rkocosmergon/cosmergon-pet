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

🔴 THE SECOND HALF OF THAT FLAW (2026-08-26, S310)
--------------------------------------------------
The paragraph above was true and incomplete, and the gap cost 19 hours of a
live agent's behaviour. ``current()`` refreshed **only when the state was
``None``** — so it fixed *"nobody ever fetched it"* and left *"nobody ever
fetches it again"* wide open. Once ``agent.state`` was populated a single time,
it was never replaced.

Measured on Comet-hand (Mac Mini, ``decider-runner.py`` — the decision loop
**without** the Pet's display poller):

* 25.08. ~09:5x — state fetched once: no fields owned, ``targets[0]`` a foreign
  field ``124b0443``.
* 25.08. 09:50 — besieged it. Correct: it was foreign.
* 25.08. 10:03 — **captured it.** It is now his own.
* until 26.08. 05:00 — **88 further sieges on that same, now self-owned field**,
  because his world picture still said "no fields, target 124b0443".

The same tree, in the same container, given a *fresh* state chose a different,
foreign target. The code was never wrong; its input was 19 hours old.

And the runner had removed its own refresh task in good faith, citing this
module: *"that was a workaround for a loop which read the state without ever
fetching it, and it has been fixed at the root instead."* The removed workaround
was the only thing keeping the state current.

Hence ``max_age_s``: a state older than one decision interval is, by definition,
stale for the next decision. The threshold is not a chosen number — the loops
pass their own ``interval_s``, so there is one source for it
(``tree_loop``/``llm_decider``). An external poller (the Pet's display) keeps
setting a *new* state object, which resets the clock; inside the Pet nothing
changes, exactly as before.
"""

from __future__ import annotations

import logging
import time
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

    1. ``agent.state`` — set by whoever polls (the Pet's display loop does),
       as long as it is younger than ``max_age_s``.
    2. ``agent.refresh_state()`` — fetched here when nobody did, **or when what
       they left behind has gone stale**.

    Keeps one counter so that a *persistent* absence is reported once at
    WARNING instead of once per round, and reports recovery too. Callers hold
    one instance per loop, mirroring how ``tree_loop`` holds its ``_Backoff``.

    Args:
        loud_after: Consecutive empty rounds before warning.
        max_age_s: Maximum age of a state before it is re-fetched. ``None``
            disables ageing — only for callers that provably keep the state
            fresh themselves. The loops pass their own ``interval_s``: a state
            older than one decision interval is stale for the next decision.
    """

    def __init__(
        self, loud_after: int = DEFAULT_LOUD_AFTER, max_age_s: float | None = None
    ) -> None:
        self._missing_rounds = 0
        self._loud_after = loud_after
        self._max_age_s = max_age_s
        self._gesehen: Any = None
        self._gesehen_um = 0.0

    def _veraltet(self, state: Any) -> bool:
        """True, wenn DIESES Zustands-Objekt hier zu lange unveraendert liegt.

        Der Vergleich ist die **Identitaet**, nicht der Inhalt: ``refresh_state()``
        baut bei jedem Abruf ein neues ``GameState`` (``GameState.from_api``).
        Ein fremder Poller — der Display-Loop des Pets — legt also laufend ein
        neues Objekt ab, und jedes neue Objekt stellt die Uhr zurueck. Damit
        aendert sich im Pet nichts, und ein Loop ohne Poller holt selbst nach.
        """
        if self._max_age_s is None:
            return False
        jetzt = time.monotonic()
        if state is not self._gesehen:
            self._gesehen = state
            self._gesehen_um = jetzt
            return False
        return (jetzt - self._gesehen_um) > self._max_age_s

    async def current(self, agent: Any) -> Any | None:
        """Return the state, fetching it if needed — or ``None`` and say so."""
        state = getattr(agent, "state", None)
        if state is None or self._veraltet(state):
            frisch = await self._fetch(agent)
            if frisch is not None:
                state = frisch
                self._gesehen = frisch
                self._gesehen_um = time.monotonic()
            # Fehlschlag bei vorhandenem Altzustand (Rate-Limit, transientes 5xx):
            # lieber alt weiterarbeiten als gar nicht — aber die Uhr NICHT
            # zurueckstellen, sonst wartet der naechste Versuch ein volles
            # Intervall auf einen Zustand, der schon veraltet ist.

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
