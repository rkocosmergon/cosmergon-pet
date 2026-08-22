"""Animierte Roboter-Augen für das 128x64-OLED — parametrisch, ohne Sprites.

HERKUNFT UND ABGRENZUNG
-----------------------
Vorbild ist die Arduino-Bibliothek **FluxGarage RoboEyes** von Dennis
Hoelscher (github.com/FluxGarage/RoboEyes), die Wall-E-/Cozmo-artige Augen auf
monochromen OLEDs zeichnet. Übernommen ist ausschließlich das **dokumentierte
Verhalten** aus ihrem README — die Konfigurationsgrößen (Breite, Höhe,
Eckenradius, Abstand), die vier Stimmungen, die Positionierung in acht
Himmelsrichtungen und der Satz an Animationen (Autoblinker, Idle, Confused,
Laugh, Flicker).

**Kein Quellcode von dort ist eingeflossen, und das ist Absicht:** RoboEyes
steht unter GPL-3.0, `cosmergon-pet` unter MIT. Eine Code-Übernahme würde das
veröffentlichte Pet auf GPL-3.0 umstellen — irreversibel. Die Bibliothek hängt
zudem an `Adafruit_GFX`; das Pet zeichnet über `luma.oled` und PIL, eine
Übernahme wäre also ohnehin eine Neuimplementierung gewesen. Das Verhalten
einer Bibliothek ist nicht geschützt, ihre Implementierung schon.

WARUM PARAMETRISCH UND NICHT ALS SPRITE
---------------------------------------
Der erste Anlauf (S306) rechnete Sprites in Blender vor. Das trug die Form,
aber nicht die Bewegung: jeder Zwischenzustand hätte ein eigenes Bild
gebraucht, und Blickwandern oder ein halb geschlossenes Lid sind stufenlos.
Parametrisch gezeichnet ist ein Blinzeln eine Zahl, die fällt — und der
Rechenaufwand liegt bei einem Bruchteil dessen, was die Ausgabe kostet
(gemessen auf dem Pi Zero 2 W, S306: Bildaufbau 0,38 ms gegen 32,7 ms für die
I²C-Übertragung, also 30,6 Bilder/s als harte Obergrenze).

AUFBAU
------
Alles Helle ist eine gezeichnete Fläche, alles Dunkle ist Grund. Die
Stimmungen entstehen durch **schwarze Lider**, die über das offene Auge gelegt
werden — nicht durch eigene Augenformen. Damit bleibt eine einzige Grundform
und jede Stimmung ist stufenlos anfahrbar.

Der Zustand wird nicht selbst getaktet: `render(now)` bekommt die Zeit vom
Aufrufer. So bleibt die Klasse ohne Thread und ohne Uhr testbar.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

DEFAULT = "default"
TIRED = "tired"
ANGRY = "angry"
HAPPY = "happy"

# Blickrichtungen als (dx, dy) in Anteilen des verfügbaren Spielraums.
POSITIONS: dict[str, tuple[float, float]] = {
    "default": (0.0, 0.0),
    "n": (0.0, -1.0),
    "ne": (1.0, -1.0),
    "e": (1.0, 0.0),
    "se": (1.0, 1.0),
    "s": (0.0, 1.0),
    "sw": (-1.0, 1.0),
    "w": (-1.0, 0.0),
    "nw": (-1.0, -1.0),
}


@dataclass
class RoboEyes:
    """Zeichnet ein Augenpaar und hält dessen Animationszustand.

    Die Maße sind Pixel auf dem Zielbild. Voreingestellt ist ein Paar, das auf
    128x64 mittig steht und ringsum Luft lässt: 2*36 + 10 = 82 px breit
    (23 px Rand je Seite), 36 px hoch (14 px oben und unten).
    """

    screen_width: int = 128
    screen_height: int = 64
    eye_width: int = 36
    eye_height: int = 36
    border_radius: int = 8
    space_between: int = 10
    cyclops: bool = False

    mood: str = DEFAULT
    position: str = "default"
    curiosity: bool = False

    autoblinker: bool = False
    blink_interval: float = 4.0
    blink_variation: float = 3.0

    idle: bool = False
    idle_interval: float = 3.0
    idle_variation: float = 2.0

    h_flicker: int = 0  # Amplitude in px, 0 = aus
    v_flicker: int = 0

    # Zeitkonstante der Blickbewegung in Sekunden: nach dieser Zeit sind rund
    # zwei Drittel des Wegs zurückgelegt. 0,12 s liest sich als lebendiger
    # Sakkaden-Sprung; darüber wirkt der Blick schwerfällig, darunter springt
    # er hart und der Eindruck "smooth animated" geht verloren.
    glaettung: float = 0.12

    # --- Laufzeitzustand (nicht konfigurieren) ------------------------------
    _offen: float = 1.0  # 1.0 = ganz offen, 0.0 = geschlossen
    _blink_bis: float = 0.0
    _naechster_blink: float = 0.0
    _naechster_idle: float = 0.0
    _anim_bis: float = 0.0
    _anim_art: str = ""
    _pos_x: float = 0.0  # aktuelle Blickrichtung, folgt der Zielrichtung nach
    _pos_y: float = 0.0
    _letzte_zeit: float | None = None
    _rng: Any = field(default_factory=random.Random)

    # ------------------------------------------------------------------ API
    def blink(self, now: float, dauer: float = 0.18) -> None:
        """Ein einzelnes Blinzeln auslösen."""
        self._blink_bis = now + dauer

    def anim_confused(self, now: float, dauer: float = 0.6) -> None:
        """Waagerechtes Zittern — die Reaktion auf etwas Unerwartetes."""
        self._anim_art, self._anim_bis = "confused", now + dauer

    def anim_laugh(self, now: float, dauer: float = 0.8) -> None:
        """Senkrechtes Wippen — Lachen."""
        self._anim_art, self._anim_bis = "laugh", now + dauer

    def set_mood(self, mood: str) -> None:
        self.mood = mood if mood in (DEFAULT, TIRED, ANGRY, HAPPY) else DEFAULT

    def set_position(self, position: str) -> None:
        self.position = position if position in POSITIONS else "default"

    # -------------------------------------------------------------- Ablauf
    def _takt(self, now: float) -> None:
        """Führt die selbstlaufenden Animationen einen Schritt weiter."""
        if self.autoblinker:
            if self._naechster_blink == 0.0:
                self._naechster_blink = now + self.blink_interval
            elif now >= self._naechster_blink:
                self.blink(now)
                self._naechster_blink = (
                    now + self.blink_interval + self._rng.random() * self.blink_variation
                )
        if self.idle:
            if self._naechster_idle == 0.0:
                self._naechster_idle = now + self.idle_interval
            elif now >= self._naechster_idle:
                self.position = self._rng.choice(list(POSITIONS))
                self._naechster_idle = (
                    now + self.idle_interval + self._rng.random() * self.idle_variation
                )

        # Lidstellung: während eines Blinzelns zu und wieder auf. Die Kurve ist
        # bewusst ein Sinus und keine Gerade — ein linear schliessendes Lid
        # liest sich mechanisch, das Auge "klappt" statt zu blinzeln.
        if now < self._blink_bis:
            rest = (self._blink_bis - now) / 0.18
            self._offen = abs(math.cos(rest * math.pi))
        else:
            self._offen = 1.0

        # Blick weich nachführen. Der Faktor wird aus dem tatsächlich
        # vergangenen dt gerechnet, nicht aus einer angenommenen Bildrate —
        # das Pet liefert keine konstante Frequenz (Netzabfragen dazwischen),
        # und ein fester Schritt pro Bild würde die Bewegung je nach Last
        # unterschiedlich schnell machen.
        erstes_bild = self._letzte_zeit is None
        dt = 0.0 if erstes_bild else max(0.0, now - self._letzte_zeit)
        self._letzte_zeit = now
        ziel_x, ziel_y = POSITIONS[self.position]
        if erstes_bild:
            # Kein Nachlauf ohne Vorgeschichte: das erste Bild steht sofort auf
            # der Zielrichtung, sonst faehrt das Pet beim Start sichtbar aus
            # der Mitte heraus. Ein wiederholtes Bild zur selben Zeit (dt == 0)
            # bewegt dagegen NICHTS — sonst springt der Blick bei jedem
            # Doppel-Render ans Ziel und die Glaettung waere wirkungslos.
            self._pos_x, self._pos_y = ziel_x, ziel_y
        elif dt > 0.0:
            anteil = 1.0 - math.exp(-dt / self.glaettung)
            self._pos_x += (ziel_x - self._pos_x) * anteil
            self._pos_y += (ziel_y - self._pos_y) * anteil

    def _versatz(self, now: float) -> tuple[int, int]:
        """Verschiebung beider Augen: Blickrichtung, Zittern, Flimmern."""
        spielraum_x = (self.screen_width - self._gesamtbreite()) // 2
        spielraum_y = (self.screen_height - self.eye_height) // 2
        dx = round(self._pos_x * spielraum_x)
        dy = round(self._pos_y * spielraum_y)

        if now < self._anim_bis:
            # 18 Hz Zittern — schnell genug, um als Vibration zu lesen, langsam
            # genug, dass es bei 30 Bildern/s nicht zu Aliasing wird.
            schwingung = math.sin(now * 18.0 * math.pi) * 4
            if self._anim_art == "confused":
                dx += int(schwingung)
            else:
                dy += int(schwingung)

        if self.h_flicker:
            dx += self._rng.randint(-self.h_flicker, self.h_flicker)
        if self.v_flicker:
            dy += self._rng.randint(-self.v_flicker, self.v_flicker)
        return dx, dy

    def _gesamtbreite(self) -> int:
        if self.cyclops:
            return self.eye_width
        return 2 * self.eye_width + self.space_between

    # ------------------------------------------------------------ Zeichnen
    def render(self, now: float, bild: Any = None) -> Any:
        """Zeichnet ein Bild des aktuellen Zustands und gibt es zurück.

        Args:
            now: Zeit in Sekunden (monoton). Der Aufrufer bestimmt den Takt.
            bild: Optionales 1-Bit-`PIL.Image`, in das gezeichnet wird. Ohne
                Angabe wird ein neues in Bildschirmgröße angelegt.
        """
        from PIL import Image, ImageDraw

        if bild is None:
            bild = Image.new("1", (self.screen_width, self.screen_height), 0)
        zeichner = ImageDraw.Draw(bild)

        self._takt(now)
        dx, dy = self._versatz(now)

        hoehe = max(2, int(self.eye_height * self._offen))
        oben = (self.screen_height - hoehe) // 2 + dy
        links = (self.screen_width - self._gesamtbreite()) // 2 + dx

        if self.cyclops:
            self._auge(zeichner, links, oben, hoehe, seite=0)
        else:
            self._auge(zeichner, links, oben, hoehe, seite=-1)
            self._auge(zeichner, links + self.eye_width + self.space_between, oben, hoehe, seite=+1)
        return bild

    def _auge(self, zeichner: Any, x: int, y: int, hoehe: int, seite: int) -> None:
        """Ein Auge samt Lid. `seite` ist -1 links, +1 rechts, 0 einäugig."""
        breite = self.eye_width
        # Neugier: am äußeren Blickrand wird das zugewandte Auge höher — der
        # Effekt, der einen starren Blick in einen interessierten verwandelt.
        # Bemessen an der TATSÄCHLICHEN Blickrichtung, nicht an der
        # angesteuerten: sonst springt die Höhe beim Richtungswechsel schlagartig,
        # während die Augen noch unterwegs sind.
        if self.curiosity and seite != 0:
            zugewandt = self._pos_x * seite  # >0, wenn dieses Auge aussen liegt
            if zugewandt > 0:
                zuwachs = int(6 * min(1.0, zugewandt))
                y -= zuwachs // 2
                hoehe += zuwachs

        radius = min(self.border_radius, breite // 2, hoehe // 2)
        zeichner.rounded_rectangle([x, y, x + breite, y + hoehe], radius=radius, fill=1)
        self._lid(zeichner, x, y, breite, hoehe, seite)

    def _lid(self, zeichner: Any, x: int, y: int, breite: int, hoehe: int, seite: int) -> None:
        """Legt das Stimmungs-Lid als SCHWARZE Fläche über das offene Auge.

        Bewusst als Abdeckung und nicht als eigene Augenform: so gibt es eine
        Grundform, und jede Stimmung ist stufenlos anfahrbar — ein halb
        gesenktes Lid ist dann eine Zahl und kein zweites Sprite.
        """
        if self.mood == DEFAULT or hoehe < 6:
            return
        tiefe = int(hoehe * 0.45)
        if self.mood == HAPPY:
            # Lid von UNTEN: das Auge wird zur Kuppel ∩ — das Lächeln sitzt
            # im Auge, wie bei Cozmo und Vector.
            #
            # Bewusst ein GERADES Rechteck: mit gerundeten Ecken bleiben links
            # und rechts zwei weisse Fuesschen stehen, weil die Rundung die
            # unteren Ecken des Auges nicht erreicht. Die Kuppel entsteht aus
            # den ohnehin runden OBEREN Ecken des Auges — unten muss glatt
            # abgeschnitten werden.
            zeichner.rectangle([x - 2, y + hoehe - tiefe, x + breite + 2, y + hoehe + 2], fill=0)
            return
        # TIRED hängt aussen, ANGRY innen — dieselbe Geometrie, gespiegelt.
        aussen_hoch = self.mood == ANGRY
        if seite < 0:
            aussen_hoch = not aussen_hoch
        if aussen_hoch:
            ecken = [(x, y - 1), (x + breite, y - 1), (x, y + tiefe)]
        else:
            ecken = [(x, y - 1), (x + breite, y - 1), (x + breite, y + tiefe)]
        zeichner.polygon(ecken, fill=0)
