"""Rule-based decision loop — drop-in alternative to ``llm_decision_loop``.

Why a separate loop? The LLM decider speaks an HTTP-provider protocol
(``provider.decide(system, memory, world, schema=...)``), while the tree
decider operates on the ``GameState`` directly via
``TreeDecider().decide(state)``. Rather than reshape one to match the
other, we keep two thin loops with the same lifecycle (``stop``-event,
``on_decision``-callback, exception-swallowing).

Use it from ``face.py`` analogous to the LLM path::

    if decider == "tree":
        from .decider_tree import TreeDecider
        from .tree_loop import tree_decision_loop
        tree_task = asyncio.create_task(
            tree_decision_loop(agent, TreeDecider(), interval_s=..., stop=stop)
        )

The loop matches the ollama-path's defensive contract: every error is
caught and logged; the loop never raises. On chronic SDK failures, the
Pet keeps polling state — only autonomous decisions pause.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from cosmergon_agent import CosmergonAgent

from .agent_state import StateSource
from .decider_tree import VALID_ACTIONS, TreeDecider

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_S = 60.0

# S297 Backoff: nach N identischen Fehlschlaegen in Folge wird die Aktion fuer
# BACKOFF_ROUNDS Runden gesperrt. Anlass: Comet-hand hat TAGELANG minuetlich
# dieselbe abgelehnte Aktion wiederholt (erst place_cells auf Denkmal-Felder,
# dann market_list ohne Ueberschuss) — ein identischer Fehlschlag traegt ab dem
# dritten Mal keine Information mehr, kostet aber je einen API-Call und einen
# Log-Eintrag pro Minute.
BACKOFF_AFTER_FAILURES = 3
BACKOFF_ROUNDS = 30

# Pet 0.4.3 (S299): soziale Kadenz (Loop-Mechanik — Tree bleibt v2.1.3).
# Der v2.1.3-duration-Fix hielt nur
# die PAKT-Drehtuer — abgelehnte Partner bleiben Server-Kandidaten, und eine
# Ablehnung kommt asynchron NACH einem success=True (der Backoff sieht also
# nie einen Fehlschlag). Gemessen 15.08.: 992 Proposes/24 h im Minutenraster,
# davon 800 rejected, Comet-hand-Reputation am tanh-Anschlag -1,0 (jede
# Ablehnung bucht -0,015 auf den Vorschlagenden, contract_manager S285).
# Kadenz-Herleitung statt Setzung: der Median-Entscheidungsabstand der
# Empfaenger-Decider liegt bei ~32,5 min (S281/S296) — wer oefter antraegt,
# als Empfaenger ueberhaupt ENTSCHEIDEN, erzeugt strukturell
# Warteschlangen-Ablehnungen. 30 Runden x 60-s-Takt ~= diese Bezugsgroesse.
# BEIDE Propose-Aktionen sperren, sonst weicht der Baum auf den Zwilling aus
# (Gate-im-Default-Zweig-Klasse).
SOZIALE_AKTIONEN = frozenset({"propose_contract", "propose_from_template"})
SOZIAL_KADENZ_ROUNDS = 30


class _Backoff:
    """Sperrt Aktionen nach wiederholten Fehlschlaegen fuer einige Runden —
    und drosselt soziale Aktionen nach ERFOLG (Kadenz, siehe Konstanten)."""

    def __init__(self) -> None:
        self._fails: dict[str, int] = {}
        self._blocked_until_round: dict[str, int] = {}
        self._round = 0

    def naechste_runde(self) -> None:
        self._round += 1

    def blocked(self) -> frozenset[str]:
        return frozenset(a for a, bis in self._blocked_until_round.items() if bis > self._round)

    def melde(self, action: str, success: bool) -> None:
        if success:
            self._fails.pop(action, None)
            self._blocked_until_round.pop(action, None)
            if action in SOZIALE_AKTIONEN:
                bis = self._round + SOZIAL_KADENZ_ROUNDS
                for a in SOZIALE_AKTIONEN:
                    self._blocked_until_round[a] = max(self._blocked_until_round.get(a, 0), bis)
                logger.info(
                    "sozial-kadenz: %s erfolgreich — Propose-Aktionen fuer %d Runden pausiert",
                    action,
                    SOZIAL_KADENZ_ROUNDS,
                )
            return
        n = self._fails.get(action, 0) + 1
        self._fails[action] = n
        if n >= BACKOFF_AFTER_FAILURES:
            self._blocked_until_round[action] = self._round + BACKOFF_ROUNDS
            self._fails.pop(action, None)
            logger.info(
                "backoff: %s nach %d Fehlschlaegen fuer %d Runden gesperrt",
                action,
                n,
                BACKOFF_ROUNDS,
            )


def _redact_params(params: dict[str, Any]) -> dict[str, Any]:
    """Same hygiene as `llm_decider._redact_params` — never log UUIDs/amounts verbatim."""
    sensitive = {"to_player_id", "amount", "field_id", "cube_id", "listing_id"}
    return {k: ("<redacted>" if k in sensitive else v) for k, v in params.items()}


async def _one_tree_decision(
    agent: CosmergonAgent,
    decider: TreeDecider,
    on_decision: Any | None,
    backoff: _Backoff | None = None,
    state_source: StateSource | None = None,
) -> None:
    """Single decision round — never raises."""
    # S306: obtain the state instead of assuming someone else supplied it.
    # This used to read `agent.state` and return on `None` with a debug line,
    # so a loop without an external poller skipped every round in silence —
    # "started" in the log, zero actions in reality. See `agent_state`.
    source = state_source or StateSource()
    state = await source.current(agent)
    if state is None:
        return

    blocked = backoff.blocked() if backoff is not None else frozenset()
    t0 = time.monotonic()
    try:
        action, params = await decider.decide(state, blocked=blocked)
    except Exception as e:
        logger.warning("tree decider failed: %s", e)
        if on_decision is not None:
            on_decision("(tree_error)", {}, time.monotonic() - t0, False)
        return

    elapsed = time.monotonic() - t0

    # Defense-in-depth: same allowlist guard as LLM path. The tree's own
    # action_fns produce only allowlisted actions, but a future regression
    # is cheap to catch here.
    if action not in VALID_ACTIONS:
        logger.warning(
            "tree emitted disallowed action %r — dropped (allowed: %s)",
            action,
            sorted(VALID_ACTIONS),
        )
        if on_decision is not None:
            on_decision("(disallowed)", {}, elapsed, False)
        return

    if action == "wait":
        logger.info("tree chose wait (%.3fs)", elapsed)
        if on_decision is not None:
            on_decision("wait", {}, elapsed, True)
        return

    try:
        result = await agent.act(action, **params)
        success = bool(getattr(result, "success", False))
    except Exception as e:
        logger.warning("agent.act(%s) failed: %s", action, e)
        success = False

    if backoff is not None:
        backoff.melde(action, success)

    logger.info(
        "tree action=%s params=%s success=%s decided_in=%.3fs",
        action,
        _redact_params(params),
        success,
        elapsed,
    )
    if on_decision is not None:
        on_decision(action, params, elapsed, success)


async def tree_decision_loop(
    agent: CosmergonAgent,
    decider: TreeDecider,
    *,
    interval_s: float = DEFAULT_INTERVAL_S,
    stop: asyncio.Event | None = None,
    on_decision: Any | None = None,
) -> None:
    """Background loop: every ``interval_s``, ask the tree decider, execute, repeat.

    Mirrors the lifecycle contract of ``llm_decision_loop``: errors caught and
    logged; the loop never exits on its own except via ``stop`` being set.

    The loop obtains the ``GameState`` itself (S306): it prefers a state that
    someone else keeps fresh — inside the Pet that is the display's polling
    task — and fetches one via ``agent.refresh_state()` when nobody does. It is
    therefore usable standalone, without a Pet around it, and a state that stays
    absent is reported at WARNING instead of skipped in silence.

    Args:
        agent: SDK agent, must already be opened via ``async with agent``.
        decider: ``TreeDecider`` instance (or any class with the same
            ``decide(state) -> (action, params)`` signature).
        interval_s: Seconds between decisions. Tree-Inferenz selbst ist
            mikrosekunden-schnell; das Intervall begrenzt die Backend-
            Action-Rate analog zum LLM-Pfad.
        stop: Optional event to terminate the loop cleanly.
        on_decision: Optional callback ``(action, params, elapsed_s, success)``
            — used by the Pet display to flash a "decider acted" indicator.
    """
    stop = stop or asyncio.Event()
    backoff = _Backoff()
    # One instance for the whole loop: the counter inside decides when a
    # missing state stops being a hiccup and becomes worth a warning.
    state_source = StateSource()
    logger.info(
        "tree_decision_loop started decider=%s interval=%.1fs",
        getattr(decider, "name", "tree"),
        interval_s,
    )
    while not stop.is_set():
        backoff.naechste_runde()
        try:
            await _one_tree_decision(agent, decider, on_decision, backoff, state_source)
        except Exception:
            # Catch-all: nothing in this loop is allowed to kill the Pet.
            logger.warning("tree_decision_loop iteration failed", exc_info=True)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_s)
        except asyncio.TimeoutError:
            continue
    logger.info("tree_decision_loop stopped")
