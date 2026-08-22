"""Verlaufskurve mit gefüllter Fläche für das 128x64-OLED (S306).

VORBILD
-------
Der Gründer gab ein Diagramm-Blatt als Vorlage ("Product statistic", oben
rechts): eine Kurve mit angelegter Fläche darunter. Auf einem farbigen Schirm
trägt dort ein Verlauf die Fläche; bei 1 Bit gibt es nur an und aus, also wird
die Fläche voll gefüllt und die Kurve durch eine helle Oberkante gebildet.

WARUM DIE FLÄCHE UND NICHT NUR DIE LINIE
----------------------------------------
Eine 1 px dünne Linie auf 128x64 ist aus einem Meter Abstand kaum zu sehen und
zerfällt bei steilen Abschnitten in einzelne Punkte. Die gefüllte Fläche liest
sich auch aus dem Augenwinkel — was zählt, ist die Silhouette der Oberkante.
Dieselbe Regel wie beim Gesicht: bei 1 Bit trägt die Form, nicht das Detail.

MASSSTAB
--------
Die Kurve wird auf ihren EIGENEN Wertebereich gespannt, nicht auf null. Ein
Konto, das zwischen 56.100 und 56.400 schwankt, wäre gegen die Nullinie eine
gerade Linie — die Bewegung ist der Punkt der Anzeige, nicht der Absolutwert.
Der steht als Zahl daneben.
"""

from __future__ import annotations

from typing import Any


def flaeche_zeichnen(
    zeichner: Any,
    werte: list[float],
    links: int,
    oben: int,
    breite: int,
    hoehe: int,
) -> tuple[float, float]:
    """Zeichnet `werte` als gefüllte Fläche in das angegebene Rechteck.

    Args:
        zeichner: `PIL.ImageDraw`-Objekt.
        werte: Messwerte, aufsteigend in der Zeit. Weniger als zwei Werte
            ergeben nichts Zeichenbares.
        links, oben, breite, hoehe: Zielrechteck in Pixeln.

    Returns:
        `(kleinster, groesster)` Wert — der Aufrufer beschriftet damit die
        Achse, ohne die Liste ein zweites Mal durchzugehen.
    """
    if len(werte) < 2:
        return (0.0, 0.0)

    tief, hoch = min(werte), max(werte)
    spanne = hoch - tief
    if spanne <= 0:
        # Völlig flacher Verlauf: eine Linie auf halber Höhe. Ohne diesen Fall
        # teilt die Skalierung durch null; mit einer Linie am unteren Rand
        # sähe ein ruhiges Konto wie ein leeres aus.
        mitte = oben + hoehe // 2
        zeichner.rectangle([links, mitte, links + breite, oben + hoehe], fill=1)
        return (tief, hoch)

    # Eine Spalte je Pixel. Mehr Werte als Spalten werden zusammengefasst,
    # indem je Spalte der SPITZENWERT genommen wird — ein Ausschlag darf beim
    # Verdichten nicht verschwinden, sonst glättet die Anzeige genau das weg,
    # wofür man auf sie schaut.
    for x in range(breite + 1):
        von = int(x * len(werte) / (breite + 1))
        bis = max(von + 1, int((x + 1) * len(werte) / (breite + 1)))
        spitze = max(werte[von:bis])
        y = oben + hoehe - int((spitze - tief) / spanne * hoehe)
        zeichner.rectangle([links + x, y, links + x, oben + hoehe], fill=1)

    return (tief, hoch)


def kurz(wert: float) -> str:
    """Kontostand knapp: 56.4k statt 56376.93 — auf 128 px zählt jedes Zeichen."""
    if abs(wert) >= 1_000_000:
        return f"{wert / 1_000_000:.1f}M"
    if abs(wert) >= 1_000:
        return f"{wert / 1_000:.1f}k"
    return f"{wert:.0f}"
