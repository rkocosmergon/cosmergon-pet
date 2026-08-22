"""Verlaufskurve als Linie mit schraffierter Flaeche fuer das 128x64-OLED (S306).

VORBILD
-------
Der Gründer gab ein Diagramm-Blatt als Vorlage ("Product statistic", oben
rechts): eine Kurve mit angelegter Fläche darunter.

LINIE MIT SCHRAFFUR, NICHT VOLLE FÜLLUNG
----------------------------------------
Erste Fassung füllte die Fläche massiv. Das las sich zwar, deckte aber die
halbe Anzeige zu und machte aus der Kurve eine blosse Silhouettenkante.
Gründer-Entscheidung 22.08.2026: **Linie mit senkrechter Schraffur darunter.**

Das trägt bei 1 Bit, weil sich die beiden Elemente in der RICHTUNG
unterscheiden und nicht in der Helligkeit — die gibt es nicht. Die Kurve ist
ein durchgehender waagerechter Zug, die Schraffur eine Folge senkrechter
Striche. Deshalb wird die Schraffur zuerst gezeichnet und die Linie darüber:
umgekehrt bräche jeder Schraffurstrich die Oberkante auf.

Die Kurve wird von Spalte zu Spalte VERBUNDEN, nicht als Punktfolge gesetzt.
Bei steilen Abschnitten springt sie sonst um mehrere Pixel und zerfällt.

MASSSTAB
--------
Die Kurve wird auf ihren EIGENEN Wertebereich gespannt, nicht auf null. Ein
Konto, das zwischen 56.100 und 56.400 schwankt, wäre gegen die Nullinie eine
gerade Linie — die Bewegung ist der Punkt der Anzeige, nicht der Absolutwert.
Der steht als Zahl daneben.
"""

from __future__ import annotations

from typing import Any


def kurve_zeichnen(
    zeichner: Any,
    werte: list[float],
    links: int,
    oben: int,
    breite: int,
    hoehe: int,
    schraffur_abstand: int = 4,
) -> tuple[float, float]:
    """Zeichnet `werte` als Linienkurve mit schraffierter Fläche darunter.

    Args:
        zeichner: `PIL.ImageDraw`-Objekt.
        werte: Messwerte, aufsteigend in der Zeit. Unter zwei Werten gibt es
            nichts zu zeichnen.
        links, oben, breite, hoehe: Zielrechteck in Pixeln.
        schraffur_abstand: Spaltenabstand der senkrechten Striche.

    Returns:
        `(kleinster, groesster)` Wert — der Aufrufer beschriftet damit die
        Achse, ohne die Liste ein zweites Mal durchzugehen.
    """
    if len(werte) < 2:
        return (0.0, 0.0)

    tief, hoch = min(werte), max(werte)
    spanne = hoch - tief
    boden = oben + hoehe

    if spanne <= 0:
        # Völlig flacher Verlauf: Linie auf halber Höhe, darunter Schraffur.
        # Ohne diesen Fall teilt die Skalierung durch null; ohne die Linie sähe
        # ein ruhiges Konto aus wie ein leeres.
        mitte = oben + hoehe // 2
        _schraffieren(zeichner, [mitte] * (breite + 1), links, boden, schraffur_abstand)
        zeichner.line([links, mitte, links + breite, mitte], fill=1)
        return (tief, hoch)

    # Eine Stützstelle je Spalte. Mehr Werte als Spalten werden verdichtet,
    # indem je Spalte der SPITZENWERT genommen wird — ein Ausschlag darf beim
    # Verdichten nicht verschwinden, sonst glättet die Anzeige genau das weg,
    # wofür man auf sie schaut.
    y_werte: list[int] = []
    for x in range(breite + 1):
        von = int(x * len(werte) / (breite + 1))
        bis = max(von + 1, int((x + 1) * len(werte) / (breite + 1)))
        spitze = max(werte[von:bis])
        y_werte.append(boden - int((spitze - tief) / spanne * hoehe))

    # Erst die Schraffur, dann die Linie darüber: so bleibt die Oberkante als
    # durchgehender Strich erkennbar. Umgekehrt würde die Schraffur sie an
    # jeder senkrechten Linie durchbrechen.
    _schraffieren(zeichner, y_werte, links, boden, schraffur_abstand)
    for x in range(breite):
        # Von Spalte zu Spalte verbinden statt Punkte zu setzen: bei steilen
        # Abschnitten springt die Kurve sonst um mehrere Pixel und zerfällt in
        # einzelne Punkte — auf 1 Bit ist sie dann keine Linie mehr.
        zeichner.line([links + x, y_werte[x], links + x + 1, y_werte[x + 1]], fill=1)
    return (tief, hoch)


def _schraffieren(zeichner: Any, y_werte: list[int], links: int, boden: int, abstand: int) -> None:
    """Senkrechte Striche von der Kurve bis zum Boden, jede `abstand` Spalten.

    Die Schraffur ersetzt die volle Füllung: sie zeigt dasselbe — was unter
    der Kurve liegt, gehört dazu — ohne die halbe Anzeige zuzudecken, und sie
    lässt die Linie als Linie stehen.
    """
    for x in range(0, len(y_werte), abstand):
        y = y_werte[x]
        if y < boden:
            zeichner.line([links + x, y + 1, links + x, boden], fill=1)


def marke_zeichnen(zeichner: Any, x: int, y: int, wert: float, nach_oben: bool, font: Any) -> None:
    """Höchst- oder Tiefstwert als Zahl mit Dreieck, auf eigenem Grund.

    Die Marke liegt ÜBER der Kurve (Gründer 22.08.2026: „die zahlen können die
    kurve verdecken … die zahlen bekommen einen hintergrund, der sie lesbar
    hält"). Der Hintergrund ist ein schwarz gefülltes Rechteck: bei einem Bit
    gibt es keine Transparenz, ohne das Loch liefen Schraffur und Ziffern
    ineinander und beides wäre unlesbar.

    Das Dreieck wird GEZEICHNET, nicht gesetzt: der Bitmap-Font des Pi kennt
    U+25B2/U+25BC nicht und zeigt an ihrer Stelle ein Ersatzkästchen mit
    Hex-Code (am Gerät geprüft).
    """
    text = kurz(wert)
    breite = 7 + 6 * len(text)
    zeichner.rectangle([x, y, x + breite, y + 8], fill=0)
    if nach_oben:
        zeichner.polygon([(x + 3, y + 1), (x + 6, y + 6), (x, y + 6)], fill=1)
    else:
        zeichner.polygon([(x, y + 2), (x + 6, y + 2), (x + 3, y + 7)], fill=1)
    zeichner.text((x + 8, y), text, font=font, fill=1)


def kurz(wert: float) -> str:
    """Kontostand knapp: 56.4k statt 56376.93 — auf 128 px zählt jedes Zeichen."""
    if abs(wert) >= 1_000_000:
        return f"{wert / 1_000_000:.1f}M"
    if abs(wert) >= 1_000:
        return f"{wert / 1_000:.1f}k"
    return f"{wert:.0f}"
