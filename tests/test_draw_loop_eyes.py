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


def test_alert_und_action_sind_im_schoner_unerreichbar() -> None:
    """Hält die Aussage im Kommentar an EYE_MOODS fest — als Rechnung, nicht als Meinung.

    Der Bildschirmschoner verlangt 30 s ohne Eingabe; `alert` gilt 0,8 s nach
    einer Drehung, `action` 2,5 s nach einer Aktion. Beide können dort also
    nicht auftreten. Wird eine der drei Konstanten verschoben, ändert sich das
    — und dann muss jemand die Augenformen für diese Zustände wirklich
    ansehen, statt sie weiter für Vorsorge zu halten.
    """
    assert face.ALERT_AFTER_ROTATION_SECONDS < face.SCREENSAVER_AFTER_SECONDS
    assert face.ACTION_FLASH_SECONDS < face.SCREENSAVER_AFTER_SECONDS


class FakeVerlaufDisplay(FakeEyesDisplay):
    """Display, das zusätzlich den Verlaufs-Schirm kann."""

    def __init__(self) -> None:
        super().__init__()
        self.verlauf_calls: list[tuple[str, int, str]] = []

    def draw_verlauf(self, name: str, werte: list[float], label: str, konto: float) -> None:
        self.verlauf_calls.append((name, len(werte), label))


def test_schirm_eins_zeigt_den_verlauf_statt_text() -> None:
    ps = _ruhender_zustand()
    ps.last_rotation_at = __import__("time").monotonic()  # gerade gedreht -> kein Schoner
    ps.balance_history = {"24h": [1.0, 2.0, 3.0], "7d": [1.0, 2.0]}
    display = FakeVerlaufDisplay()
    _einmal_zeichnen(display, ps)
    assert display.verlauf_calls, "Verlaufs-Schirm wurde nicht gezeichnet"
    assert display.draw_calls == 0, "zusätzlich den Textschirm gezeichnet"


def test_geoeffnetes_menue_zeigt_wieder_text() -> None:
    """Im Menü muss die Auswahl lesbar bleiben — dort kein Diagramm."""
    ps = _ruhender_zustand()
    ps.last_rotation_at = __import__("time").monotonic()
    ps.menu_open = True
    display = FakeVerlaufDisplay()
    _einmal_zeichnen(display, ps)
    assert display.draw_calls > 0
    assert not display.verlauf_calls


def test_andere_schirme_bleiben_text() -> None:
    ps = _ruhender_zustand()
    ps.last_rotation_at = __import__("time").monotonic()
    ps.current_screen = 3
    display = FakeVerlaufDisplay()
    _einmal_zeichnen(display, ps)
    assert display.draw_calls > 0
    assert not display.verlauf_calls


def test_zeitfenster_wechseln_und_kommen_zurueck() -> None:
    """Der Wechsel hängt an der Uhr, nicht an der Bildrate."""
    schritt = face.HISTORY_SWITCH_SECONDS
    gesehen = {face.aktuelles_fenster(n * schritt)[0] for n in range(len(face.HISTORY_WINDOWS))}
    assert gesehen == {w for w, _ in face.HISTORY_WINDOWS}
    # Innerhalb eines Intervalls bleibt es stehen.
    assert face.aktuelles_fenster(1.0) == face.aktuelles_fenster(schritt - 1.0)
    # Und nach einer vollen Runde ist es wieder das erste.
    assert face.aktuelles_fenster(0.0) == face.aktuelles_fenster(
        schritt * len(face.HISTORY_WINDOWS)
    )


def test_jedes_fenster_hat_eine_beschriftung() -> None:
    for schluessel, label in face.HISTORY_WINDOWS:
        assert schluessel and label, f"{schluessel}: leere Beschriftung"
        assert len(label) <= 21, f"{label}: passt nicht in eine Zeile"
