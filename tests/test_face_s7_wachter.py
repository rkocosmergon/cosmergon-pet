"""Waechter: Schirm 7 mit outcome=null, Menueauswahl ueber den State-Poll hinweg (cos20 #587)."""

from __future__ import annotations

import asyncio

from cosmergon_agent.state import GameState

from cosmergon_pet import face

# Eine Entscheidung so, wie GET /agents/{id}/decisions sie liefert (agent_game.py:156-167),
# Werte aus Prod (agent_decisions, 27.10.2026 06:09:39Z): outcome ist NULL. 964 solche Zeilen
# bei llm-Agenten, eine davon bei einem Agenten mit menschlichem Besitzer.
ENTSCHEIDUNG_OHNE_AUSGANG = {
    "tick": 221592,
    "action": "place_cells",
    "params": {"preset": "block"},
    "reasoning": "Grow the field.",
    "outcome": None,
    "journal": None,
    "focus": 100.0,
    "created_at": "2026-10-27T06:09:39.482640+00:00",
}


def _ereignis(ps: face.PetState, event: str) -> None:
    asyncio.run(face.handle_event(event, ps, None, 1000.0))  # type: ignore[arg-type]


def test_s7_k116_schirm7_ohne_eigene_aktion() -> None:
    ps = face.PetState(current_screen=6, last_decision=dict(ENTSCHEIDUNG_OHNE_AUSGANG))
    zeilen = face.render_screen(ps, 1000.0)
    assert any("place_cells"[:12] in z for z in zeilen)


def test_s7_k116_schirm7_mit_eigener_aktion() -> None:
    ps = face.PetState(
        current_screen=6,
        last_decision=dict(ENTSCHEIDUNG_OHNE_AUSGANG),
        last_user_action={"action": "evolve", "status": "ok", "detail": "-1000E", "ts": 1.0},
    )
    zeilen = face.render_screen(ps, 1000.0)
    assert any(z.startswith("LLM:") for z in zeilen)


def _zustand(katastrophe: str | None, zellen: int) -> GameState:
    """Ein Zustand in Prod-Form (Feldnamen wie /agents/{id}/state)."""
    return GameState.from_api(
        {
            "agent_id": "a1",
            "agent_type": "independent_agent",
            "energy_balance": 5000.0,
            "fields": [{"id": "f1", "cube_id": "c1", "z_position": 0, "active_cell_count": zellen}],
            "cubes": [],
            "universe_cubes": [],
            "ranking": {},
            "focus": {},
            "world_briefing": {
                "agent_situation": {
                    "fields_owned": 1,
                    "fields_without_cells": 1 if zellen == 0 else 0,
                    "affordable_presets": ["block"],
                    "active_catastrophe": katastrophe,
                }
            },
        }
    )


def _waehle(ps: face.PetState, ziel: str) -> None:
    """Echter Eingang: Klick auf Schirm 1 oeffnet das Menue, Drehen nach rechts bis zum Ziel."""
    _ereignis(ps, face.InputEvent.CLICK)
    assert ps.menu_open is True
    eintraege = face.build_menu(ps.game_state, ps.paused)
    for _ in range([k for _, k in eintraege].index(ziel)):
        _ereignis(ps, face.InputEvent.ROT_RIGHT)
    assert face.build_menu(ps.game_state, ps.paused)[ps.menu_index][1] == ziel


def test_s7_k117_menue_schrumpft_zwischen_drehen_und_klick() -> None:
    """Auswahl auf dem letzten Eintrag („Close Menu“); der State-Poll (alle 30 s) bringt einen
    Zustand ohne Katastrophe und mit Zellen — das Menue ist zwei Eintraege kuerzer."""
    ps = face.PetState(game_state=_zustand("plague", 0))
    _waehle(ps, "close")
    ps.game_state = _zustand(None, 42)

    _ereignis(ps, face.InputEvent.CLICK)

    assert ps.menu_open is False  # „Close Menu“ war gewaehlt


def test_s7_k117_klick_fuehrt_gewaehlten_eintrag_aus() -> None:
    """Auswahl auf „Set Compass“; nach dem Poll ist das Menue kuerzer, und an der alten Position
    steht ein anderer Eintrag („Close Menu“)."""
    ps = face.PetState(game_state=_zustand("plague", 0))
    _waehle(ps, "compass")
    ps.game_state = _zustand(None, 42)

    _ereignis(ps, face.InputEvent.CLICK)

    assert ps.compass_submenu is True
