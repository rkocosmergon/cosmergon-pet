"""The face follows the server's energy trend (cos20 #489).

The server sends ``world_briefing.agent_situation.energy_trend`` as ``rising``, ``stable`` or
``declining``. Until 0.8.12 the face checked ``falling``, a word the state never sent: the pet
was never sad when its energy fell, and the trend line showed the raw word ``declining``.
Against 0.8.11 both tests are red.
"""

from __future__ import annotations

from cosmergon_agent.state import GameState

from cosmergon_pet.face import PetState, _render_energy, mood_from_state


def _pet(trend: str) -> PetState:
    state = GameState.from_api(
        {
            "agent_id": "a",
            "energy_balance": 1000.0,
            "world_briefing": {
                "total_agents": 10,
                "your_rank": 3,
                "market_summary": "",
                "agent_situation": {"fields_owned": 1, "energy_trend": trend},
            },
        }
    )
    return PetState(game_state=state)


def test_falling_energy_makes_the_face_struggle() -> None:
    assert mood_from_state(_pet("declining"), now=1e9) == "struggling"
    assert mood_from_state(_pet("rising"), now=1e9) == "thriving"
    assert mood_from_state(_pet("stable"), now=1e9) == "content"


def test_trend_line_shows_an_arrow_word_not_the_raw_value() -> None:
    zeilen = _render_energy(_pet("declining"), now=1e9)
    assert any(z.strip() == "Trend:  down" for z in zeilen), zeilen
