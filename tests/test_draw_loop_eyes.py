"""Tests für die Anbindung der gezeichneten Augen an den Zeichen-Ablauf.

Warum es diese Tests gibt: `draw_eyes` existiert nur auf `OledDisplay` und
läuft damit ausschliesslich auf dem Gerät. Ohne Test hier wäre der erste
tatsächliche Durchlauf der auf der Hardware — und ein Tippfehler im
Ablauf fiele erst dort auf, wo niemand einen Stacktrace sieht (der Ablauf
fängt jede Ausnahme ab und schreibt sie ins Log).
"""
from __future__ import annotations

import asyncio

from cosmergon_pet import face


class FakeEyesDisplay:
    """Display mit Augen-Pfad — steht für `OledDisplay` auf dem Gerät."""

    def __init__(self) -> None:
        self.eyes_calls: list[tuple[str, bool]] = []
        self.draw_calls = 0

    def draw(self, lines: list[str]) -> None:
        self.draw_calls += 1

    def draw_eyes(self, mood: str, now: float, blink: bool = False) -> None:
        self.eyes_calls.append((mood, blink))


class FakeAsciiDisplay:
    """Display ohne Augen-Pfad — steht für die Terminal-Simulation."""

    def __init__(self) -> None:
        self.face_calls: list[str] = []
        self.draw_calls = 0

    def draw(self, lines: list[str]) -> None:
        self.draw_calls += 1

    def draw_big_face(self, face_str: str, cell_count: int = 0) -> None:
        self.face_calls.append(face_str)


def _einmal_zeichnen(display: object, ps: face.PetState) -> None:
    """Lässt den Zeichen-Ablauf genau einen Durchgang machen."""

    async def lauf() -> None:
        stop = asyncio.Event()

        async def stoppen() -> None:
            await asyncio.sleep(0.01)
            stop.set()

        await asyncio.gather(face._draw_loop(display, ps, stop), stoppen())

    asyncio.run(lauf())


def _ruhender_zustand() -> face.PetState:
    """Zustand, der den Bildschirmschoner auslöst: Bildschirm 1, kein Menü."""
    ps = face.PetState()
    ps.current_screen = 0
    ps.menu_open = False
    ps.last_rotation_at = 0.0
    ps.last_action_at = 0.0
    return ps


def test_ruhender_zustand_zeichnet_augen_statt_ascii() -> None:
    display = FakeEyesDisplay()
    _einmal_zeichnen(display, _ruhender_zustand())
    assert display.eyes_calls, "der Augen-Pfad wurde nicht aufgerufen"
    assert display.draw_calls == 0, "es wurde zusätzlich der Textschirm gezeichnet"


def test_ohne_augen_pfad_bleibt_es_beim_ascii_gesicht() -> None:
    """Die Terminal-Simulation darf durch den Umbau nicht ausfallen."""
    display = FakeAsciiDisplay()
    _einmal_zeichnen(display, _ruhender_zustand())
    assert display.face_calls, "das ASCII-Gesicht wurde nicht gezeichnet"
    assert display.face_calls[0].startswith("("), display.face_calls[0]


def test_nicht_ruhend_zeichnet_den_textschirm() -> None:
    ps = _ruhender_zustand()
    ps.menu_open = True
    display = FakeEyesDisplay()
    _einmal_zeichnen(display, ps)
    assert display.draw_calls > 0
    assert not display.eyes_calls


def test_abfrage_loest_ein_blinzeln_aus() -> None:
    """Das Pet blinzelt, wenn es Daten holt — sonst wäre der Blinzler Deko."""
    ps = _ruhender_zustand()
    import time

    ps.last_state_poll_at = time.monotonic()
    display = FakeEyesDisplay()
    _einmal_zeichnen(display, ps)
    assert display.eyes_calls[0][1] is True, "kein Blinzeln nach einer Abfrage"


def test_ohne_abfrage_kein_blinzeln() -> None:
    ps = _ruhender_zustand()
    ps.last_state_poll_at = 0.0
    ps.last_events_poll_at = 0.0
    ps.last_decisions_poll_at = 0.0
    display = FakeEyesDisplay()
    _einmal_zeichnen(display, ps)
    # Der Ablauf läuft mit monotoner Zeit; 0.0 liegt weit zurück.
    assert display.eyes_calls[0][1] is False


def test_jeder_zustand_hat_eine_augenform() -> None:
    """`EYE_MOODS` muss alle Zustände abdecken, die `mood_from_state` liefert.

    Die Referenzmenge kommt aus `FACES` — der Tabelle, die schon vorher jede
    mögliche Stimmung auflisten musste. Eine eigene Liste hier wäre eine zweite
    Quelle für dieselbe Frage und würde beim nächsten neuen Zustand veralten.
    """
    assert set(face.EYE_MOODS) == set(face.FACES)


def test_augenformen_verweisen_nur_auf_bekannte_stimmungen() -> None:
    from cosmergon_pet.robo_eyes import ANGRY, DEFAULT, HAPPY, TIRED

    erlaubt = {DEFAULT, TIRED, ANGRY, HAPPY}
    for zustand, (stimmung, hoehe, _) in face.EYE_MOODS.items():
        assert stimmung in erlaubt, f"{zustand}: unbekannte Stimmung {stimmung}"
        assert 0.0 < hoehe <= 2.0, f"{zustand}: unplausibler Höhenfaktor {hoehe}"
