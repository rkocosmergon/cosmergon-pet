"""Tests für die animierten Roboter-Augen.

Die ersten beiden Tests halten die zwei Fehler fest, die beim Bau tatsächlich
aufgetreten sind — sie sind kein Selbstzweck, sondern die Gegenprobe:

  * Das Lid der Stimmung "happy" war zunächst ein Rechteck MIT gerundeten
    Ecken. Dadurch blieben unten links und rechts zwei weisse Füsschen stehen,
    weil die Rundung die unteren Ecken des Auges nicht erreichte.
  * Die Blickbewegung sprang, weil die Position ohne Zwischenschritte gesetzt
    wurde. Das Vorbild heisst "smoothly animated"; ohne Interpolation ist
    genau das nicht gegeben.
"""
from __future__ import annotations

from cosmergon_pet.robo_eyes import ANGRY, DEFAULT, HAPPY, TIRED, RoboEyes


def _gesetzt(bild, x: int, y: int) -> bool:
    return bool(bild.load()[x, y])


def _spalten_mit_pixeln(bild, zeile: int) -> list[int]:
    px = bild.load()
    return [x for x in range(bild.size[0]) if px[x, zeile]]


def _bloecke(bild, zeile: int) -> int:
    """Zahl der zusammenhängenden weissen Abschnitte in einer Bildzeile."""
    spalten = _spalten_mit_pixeln(bild, zeile)
    if not spalten:
        return 0
    return 1 + sum(1 for a, b in zip(spalten, spalten[1:]) if b - a > 1)


def test_kein_auge_zerfaellt_in_mehrere_bloecke() -> None:
    """Pro Zeile höchstens zwei Blöcke — einer je Auge.

    Der erste Anlauf zeichnete das "happy"-Lid mit gerundeten Ecken; dadurch
    blieben unten links und rechts zwei weisse Füsschen stehen und jedes Auge
    zerfiel in DREI Blöcke. Ein Test auf eine einzelne Bildzeile fand das
    nicht — die Füsschen sassen auf Höhe der Lid-Ecken, nicht an der
    Unterkante. Geprüft wird deshalb jede Zeile, und die Bedingung ist die
    Eigenschaft selbst: ein Auge ist pro Zeile EIN Abschnitt.
    """
    for mood in (DEFAULT, HAPPY, TIRED, ANGRY):
        bild = RoboEyes(mood=mood).render(0.0)
        for zeile in range(bild.size[1]):
            assert _bloecke(bild, zeile) <= 2, (
                f"{mood}: Zeile {zeile} zerfällt in {_bloecke(bild, zeile)} Blöcke"
            )


def test_happy_ist_eine_kuppel() -> None:
    """Oben rund, unten glatt abgeschnitten — und das Auge bleibt sichtbar."""
    augen = RoboEyes(mood=HAPPY)
    bild = augen.render(0.0)
    oben = (augen.screen_height - augen.eye_height) // 2
    assert _spalten_mit_pixeln(bild, oben + 3), "die Kuppel fehlt"
    assert _spalten_mit_pixeln(bild, oben + augen.eye_height - 2) == [], (
        "das untere Lid deckt die Augenunterkante nicht ab"
    )


def test_blick_faehrt_weich_und_nicht_sprunghaft() -> None:
    """Zwischen Ausgangs- und Zielrichtung müssen Zwischenstände liegen."""
    augen = RoboEyes()
    augen.render(0.0)  # erstes Bild legt die Ausgangslage fest
    start = min(_spalten_mit_pixeln(augen.render(0.04), 32))

    augen.set_position("e")
    kanten = [min(_spalten_mit_pixeln(augen.render(0.04 + n / 25.0), 32))
              for n in range(1, 13)]

    assert kanten[-1] > start, "der Blick erreicht die Zielrichtung nicht"
    assert len(set(kanten)) >= 4, f"die Bewegung springt statt zu fahren: {kanten}"
    # Sakkade: der erste Schritt ist der grösste, danach wird abgebremst.
    assert (kanten[0] - start) > (kanten[-1] - kanten[-2])


def test_erstes_bild_steht_sofort_auf_der_zielrichtung() -> None:
    """Ohne Vorgeschichte kein Nachlauf — sonst faehrt das Pet beim Start aus der Mitte."""
    mitte = RoboEyes()
    links = RoboEyes(position="w")
    assert min(_spalten_mit_pixeln(links.render(0.0), 32)) < min(
        _spalten_mit_pixeln(mitte.render(0.0), 32)
    )


def test_blinzeln_schliesst_und_oeffnet_wieder() -> None:
    augen = RoboEyes()
    offen_vorher = len(_spalten_mit_pixeln(augen.render(0.0), 32))
    augen.blink(0.0, dauer=0.18)
    # Mitte des Blinzelns: das Auge ist deutlich flacher.
    bild = augen.render(0.09)
    hoehe = sum(1 for y in range(64) if _gesetzt(bild, 64, y))
    assert hoehe < augen.eye_height / 2, "das Lid schliesst nicht"
    # Danach wieder ganz offen.
    assert len(_spalten_mit_pixeln(augen.render(0.30), 32)) == offen_vorher


def test_cyclops_zeichnet_genau_einen_block() -> None:
    augen = RoboEyes(cyclops=True, eye_width=56)
    spalten = _spalten_mit_pixeln(augen.render(0.0), 32)
    assert spalten, "kein Auge gezeichnet"
    # Ein durchgehender Block: keine Lücke zwischen erster und letzter Spalte.
    assert spalten == list(range(spalten[0], spalten[-1] + 1))


def test_zwei_augen_haben_eine_luecke() -> None:
    augen = RoboEyes()
    spalten = _spalten_mit_pixeln(augen.render(0.0), 32)
    assert spalten != list(range(spalten[0], spalten[-1] + 1)), "die Augen kleben"


def test_stimmungen_erzeugen_verschiedene_bilder() -> None:
    bilder = {m: RoboEyes(mood=m).render(0.0).tobytes()
              for m in (DEFAULT, HAPPY, TIRED, ANGRY)}
    assert len(set(bilder.values())) == 4, "zwei Stimmungen sehen gleich aus"


def test_lider_sitzen_auf_beiden_augen_gleich() -> None:
    """Jede Stimmung ist IN SICH links-rechts-symmetrisch.

    Ein schiefes Lid — nur auf einem Auge, oder auf beiden in dieselbe
    Richtung statt gespiegelt — ist der naheliegende Fehler bei dieser
    Geometrie und würde sofort als Gesichtslähmung gelesen.

    Geprüft wird über die Pixelzahl je Hälfte, nicht über einen exakten
    Spiegelvergleich: das Augenpaar ist auf Spalte 64 zentriert, die
    Spiegelachse eines 128 px breiten Bildes liegt aber bei 63,5. Ein
    `ImageOps.mirror`-Vergleich würde an diesem halben Pixel scheitern, ohne
    dass etwas schief wäre.
    """
    for mood in (DEFAULT, HAPPY, TIRED, ANGRY):
        bild = RoboEyes(mood=mood).render(0.0)
        px = bild.load()
        links = sum(1 for x in range(64) for y in range(64) if px[x, y])
        rechts = sum(1 for x in range(64, 128) for y in range(64) if px[x, y])
        assert links == rechts, f"{mood}: {links} px links, {rechts} px rechts"


def test_unbekannte_werte_fallen_auf_den_standard_zurueck() -> None:
    augen = RoboEyes()
    augen.set_mood("euphorisch")
    augen.set_position("nordnordwest")
    assert augen.mood == DEFAULT
    assert augen.position == "default"
