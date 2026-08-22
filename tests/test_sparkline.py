"""Tests für die Verlaufskurve.

Zwei Eigenschaften tragen die Anzeige und stehen deshalb hier: die Fläche muss
auf den EIGENEN Wertebereich gespannt sein (sonst ist ein Konto, das um 0,5 %
schwankt, eine gerade Linie), und beim Verdichten vieler Werte auf 128 Spalten
darf kein Ausschlag verschwinden — sonst glättet die Anzeige genau das weg,
wofür man auf sie schaut.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

from cosmergon_pet.sparkline import flaeche_zeichnen, kurz


def _leinwand(breite: int = 128, hoehe: int = 64):
    bild = Image.new("1", (breite, hoehe), 0)
    return bild, ImageDraw.Draw(bild)


def _hoehen(bild, breite: int, oben: int, hoehe: int) -> list[int]:
    """Je Spalte: wie viele Pixel die Fläche hoch ist."""
    px = bild.load()
    return [
        sum(1 for y in range(oben, oben + hoehe + 1) if px[x, y]) for x in range(breite + 1)
    ]


def test_steigender_verlauf_wird_nach_rechts_hoeher() -> None:
    bild, d = _leinwand()
    flaeche_zeichnen(d, list(range(50)), 0, 12, 127, 39)
    h = _hoehen(bild, 127, 12, 39)
    assert h[-1] > h[0], f"Fläche steigt nicht: {h[0]} -> {h[-1]}"


def test_massstab_folgt_dem_eigenen_wertebereich() -> None:
    """Ein Konto um 56.000, das um 300 schwankt, muss Bewegung zeigen.

    Gegen null skaliert wären die 300 Einheiten 0,3 px hoch — eine gerade
    Linie. Die Bewegung ist aber der Zweck der Anzeige; der Absolutwert steht
    als Zahl daneben.
    """
    bild, d = _leinwand()
    flaeche_zeichnen(d, [56000, 56150, 56300, 56100, 56250], 0, 12, 127, 39)
    h = _hoehen(bild, 127, 12, 39)
    assert max(h) - min(h) > 20, f"Verlauf zu flach dargestellt: {min(h)}..{max(h)}"


def test_ausschlag_ueberlebt_das_verdichten() -> None:
    """500 Werte auf 128 Spalten: eine einzelne Spitze darf nicht verschwinden."""
    werte = [10.0] * 500
    werte[250] = 90.0
    bild, d = _leinwand()
    flaeche_zeichnen(d, werte, 0, 12, 127, 39)
    h = _hoehen(bild, 127, 12, 39)
    assert max(h) > min(h) + 20, f"Spitze weggeglättet: {min(h)}..{max(h)}"


def test_flacher_verlauf_ergibt_eine_linie_auf_halber_hoehe() -> None:
    """Ein ruhiges Konto darf nicht wie ein leeres aussehen."""
    bild, d = _leinwand()
    tief, hoch = flaeche_zeichnen(d, [4200.0] * 40, 0, 12, 127, 39)
    h = _hoehen(bild, 127, 12, 39)
    assert tief == hoch == 4200.0
    assert all(x > 0 for x in h), "flacher Verlauf zeichnet nichts"
    assert max(h) < 39, "flacher Verlauf füllt die ganze Höhe"


def test_zu_wenige_werte_zeichnen_nichts() -> None:
    bild, d = _leinwand()
    assert flaeche_zeichnen(d, [1.0], 0, 12, 127, 39) == (0.0, 0.0)
    assert not any(bild.load()[x, y] for x in range(128) for y in range(64))


def test_die_flaeche_bleibt_im_zugewiesenen_rechteck() -> None:
    """Nichts darf in die Kopfzeile oder auf den Namen laufen."""
    bild, d = _leinwand()
    flaeche_zeichnen(d, list(range(100)), 0, 12, 127, 39)
    px = bild.load()
    assert not any(px[x, y] for x in range(128) for y in range(0, 12)), "ragt nach oben"
    assert not any(px[x, y] for x in range(128) for y in range(52, 64)), "ragt nach unten"


def test_kurz_fasst_grosse_zahlen_zusammen() -> None:
    assert kurz(56376.93) == "56.4k"
    assert kurz(4200) == "4.2k"
    assert kurz(950) == "950"
    assert kurz(3_038_198) == "3.0M"
    assert kurz(-1500) == "-1.5k"
