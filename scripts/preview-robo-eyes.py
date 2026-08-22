#!/usr/bin/env python3
"""Vorschau der animierten Roboter-Augen — ohne Hardware.

Erzeugt zwei Dateien:
  * `robo-eyes-moods.png`  — Kontaktblatt aller Stimmungen und Blickrichtungen,
    jede Kachel 4x vergrössert, damit Pixel als Pixel sichtbar bleiben.
  * `robo-eyes.gif`        — die Bewegung: Autoblinker, Blickwandern, Lachen,
    Verwirrung. Ein Standbild kann davon nichts zeigen.

    python3 scripts/preview-robo-eyes.py [zielverzeichnis]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PIL import Image, ImageDraw

from cosmergon_pet.robo_eyes import ANGRY, DEFAULT, HAPPY, TIRED, RoboEyes

ZOOM = 4
SPALTEN = 4
FPS = 25

KACHELN: list[tuple[str, dict]] = [
    ("default", {"mood": DEFAULT}),
    ("happy", {"mood": HAPPY}),
    ("tired", {"mood": TIRED}),
    ("angry", {"mood": ANGRY}),
    ("blick N", {"mood": DEFAULT, "position": "n"}),
    ("blick O", {"mood": DEFAULT, "position": "e"}),
    ("blick SW", {"mood": DEFAULT, "position": "sw"}),
    ("neugierig O", {"mood": DEFAULT, "position": "e", "curiosity": True}),
    ("halb zu", {"mood": DEFAULT, "_offen": 0.55}),
    ("fast zu", {"mood": DEFAULT, "_offen": 0.2}),
    ("einaeugig", {"mood": DEFAULT, "cyclops": True, "eye_width": 56}),
    ("schmal", {"mood": DEFAULT, "eye_height": 18}),
]


def kontaktblatt(ziel: Path) -> None:
    kw, kh = 128 * ZOOM, 64 * ZOOM + 18
    zeilen = (len(KACHELN) + SPALTEN - 1) // SPALTEN
    blatt = Image.new("RGB", (SPALTEN * kw, zeilen * kh), (24, 24, 28))
    stift = ImageDraw.Draw(blatt)
    for i, (name, cfg) in enumerate(KACHELN):
        offen = cfg.pop("_offen", None)
        augen = RoboEyes(**cfg)
        bild = augen.render(0.0)
        if offen is not None:
            # Lidstellung direkt setzen: der Blink-Verlauf ist zeitabhaengig,
            # fuer ein Standbild brauchen wir den Zwischenstand ohne Uhr.
            augen.eye_height = max(2, int(augen.eye_height * offen))
            bild = augen.render(0.0)
        x, y = (i % SPALTEN) * kw, (i // SPALTEN) * kh
        blatt.paste(bild.convert("RGB").resize((128 * ZOOM, 64 * ZOOM), Image.NEAREST), (x, y))
        stift.text((x + 6, y + 64 * ZOOM + 4), name, fill=(150, 150, 160))
    blatt.save(ziel)
    print(f"{ziel}  ({len(KACHELN)} Kacheln)")


def bewegung(ziel: Path, sekunden: float = 8.0) -> None:
    """Eine durchgehende Szene — so, wie das Pet im Ruhezustand aussieht."""
    augen = RoboEyes(
        autoblinker=True,
        blink_interval=1.6,
        blink_variation=1.0,
        idle=True,
        idle_interval=1.4,
        idle_variation=0.8,
        curiosity=True,
    )
    augen._rng.seed(7)  # reproduzierbare Vorschau
    bilder: list[Image.Image] = []
    schritt = 1.0 / FPS
    for n in range(int(sekunden * FPS)):
        t = n * schritt
        if abs(t - 3.0) < schritt / 2:
            augen.set_mood(HAPPY)
            augen.anim_laugh(t)
        if abs(t - 5.0) < schritt / 2:
            augen.set_mood(ANGRY)
            augen.anim_confused(t)
        if abs(t - 6.5) < schritt / 2:
            augen.set_mood(TIRED)
        bilder.append(augen.render(t).convert("P"))
    bilder[0].save(ziel, save_all=True, append_images=bilder[1:], duration=int(1000 / FPS), loop=0)
    print(f"{ziel}  ({len(bilder)} Bilder, {sekunden:.0f} s)")


def main() -> None:
    ziel = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    ziel.mkdir(parents=True, exist_ok=True)
    kontaktblatt(ziel / "robo-eyes-moods.png")
    bewegung(ziel / "robo-eyes.gif")


if __name__ == "__main__":
    main()
