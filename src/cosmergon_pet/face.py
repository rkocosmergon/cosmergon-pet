"""Cosmergon Pet — Stage 1: Pet mode.

Your AI agent lives on a 128x64 OLED: a face plus eight info screens,
controlled by a single KY-040 rotary push knob.

Build guide: guide/cosmergon-pet-bauanleitung.pdf (this repo)
Repo:        github.com/rkocosmergon/cosmergon-pet

Hardware (40-pin RPi: Zero 2 W, 3, 4, 5):
    OLED 1.3" SH1106 I2C   -> VCC=Pin1, GND=Pin6, SDA=Pin3, SCL=Pin5
    KY-040 rotary encoder  -> CLK=Pin11, DT=Pin13, SW=Pin15, VCC=Pin17, GND=Pin9

Install (one-line):
    curl -sL https://raw.githubusercontent.com/rkocosmergon/cosmergon-pet/main/install/install.sh \
      | bash

Or manually:
    sudo raspi-config nonint do_i2c 0   # enable I2C, then reboot
    python3 -m venv ~/cosmergon-env && source ~/cosmergon-env/bin/activate
    pip install git+https://github.com/rkocosmergon/cosmergon-pet
    cosmergon-pet

Simulation (no RPi hardware required):
    cosmergon-pet --simulate

Eight info screens (rotate to scroll; click on screen 1 opens the action menu):
    1 face + mood            /health
    2 energy + rank          /state
    3 territory              /state
    4 events                 /events
    5 benchmark              /state
    6 journal                /decisions
    7 last action            /decisions
    8 rules                  /state

Controls:
    Rotate            Scroll through screens / menu entries
    Short press       On screen 1: open action menu
                      In menu: execute selected action
                      Otherwise: jump back to screen 1
    Long press >1s    Pause/resume agent (or leave the menu)

Screensaver:
    After 30 s of no input on screen 1 the display switches to a pair of
    animated robot eyes filling the whole panel (`cosmergon_pet.robo_eyes`).
    They blink, look around and change shape with the agent's mood. The first
    encoder turn or click brings back the regular screen 1 immediately.

    The eyes blink whenever a backend poll fires — the agent fetching data is
    what makes it close its eyes for a moment. Without that coupling the
    blinking would be decoration; this way the face actually reports something.

    In `--simulate` there are no pixels, so the console keeps printing the
    ASCII face (`( ^__^ )`) plus the cell dots. Both paths receive the same
    mood; only the rendering differs.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from cosmergon_agent import CosmergonAgent
from cosmergon_agent.state import GameState

logger = logging.getLogger("cosmergon-pet")

# --- GPIO pins (BCM numbering) ----------------------------------------------
ENC_CLK = 17  # Pin 11
ENC_DT = 27  # Pin 13
ENC_SW = 22  # Pin 15

# --- Timing -----------------------------------------------------------------
DISPLAY_REFRESH_HZ = 10  # redraw the display (10 FPS is plenty for OLED)
# The screensaver draws ANIMATED eyes, so it needs a higher rate: at 10 FPS a
# 0.18 s blink would be two frames and read as a glitch. The hardware ceiling
# is 30.6 FPS (measured on a Pi Zero 2 W, S306: 32.7 ms per I2C transfer), so
# 20 FPS leaves headroom. It does NOT cost 65 % bus load in practice — the
# display only transfers when the image actually changed, and a resting face
# changes in roughly a third of the frames.
SCREENSAVER_REFRESH_HZ = 20
STATE_POLL_SECONDS = 30  # /state poll; on_tick also fires every ~60 s
DECISION_POLL_SECONDS = 90  # /decisions less often — saves API calls
EVENTS_POLL_SECONDS = 45  # /events
LONGPRESS_SECONDS = 1.0  # long-press threshold
DORMANT_AFTER_HOURS = 24  # ( z__z ) if no decision in N hours
ACTION_FLASH_SECONDS = 2.5  # ( >__< ) for N seconds after an action
ALERT_AFTER_ROTATION_SECONDS = 0.8  # ( o__o ) when the encoder is being turned
SCREENSAVER_AFTER_SECONDS = 30  # big-face screensaver if idle on screen 1
SCREENSAVER_BLINK_DURATION = 0.3  # px-eye blink after a backend poll
SCREENSAVER_FONT_MAX_SIZE = 40  # px; auto-shrink starts here, never overshoots display
SCREENSAVER_FONT_MIN_SIZE = 14  # px; below this we give up and use the default font
DISPLAY_WIDTH_PX = 128
DISPLAY_HEIGHT_PX = 64
# TrueType fallback list — first one that exists wins. Monospace matters
# here so the parentheses, underscores and caret/tilde line up evenly
# (proportional fonts squeeze the underscores and stretch the brackets,
# breaking the face shape). DejaVu Sans Mono ships with Raspberry Pi OS.
SCREENSAVER_FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
)

# --- Faces ------------------------------------------------------------------
FACES = {
    "thriving": "( ^__^ )",
    "content": "( -__- )",
    "struggling": "( ;__; )",
    "dormant": "( z__z )",
    "alert": "( o__o )",
    "action": "( >__< )",
}

# Wie ein Pet-Zustand als Augenpaar aussieht: (Stimmung, Höhenfaktor, Neugier).
#
# Das Mapping ist absichtlich schmal — vier Stimmungen und ein Höhenfaktor
# reichen für alle sechs Zustände, weil die Höhe stufenlos ist. `dormant` ist
# kein eigener Gesichtsausdruck, sondern ein fast geschlossenes Auge; `action`
# ist keine Wut, sondern ein zusammengekniffener Blick.
#
# ANGRY ist bewusst NICHT belegt: kein Zustand des Pets bedeutet Zorn. Die
# Stimmung bleibt trotzdem in `robo_eyes`, weil sie zum übernommenen
# Verhaltensumfang gehört und ein späterer Zustand (etwa ein Angriff auf eigene
# Felder) sie brauchen könnte.
#
# ⚠ `alert` und `action` sind hier VORSORGE, keine sichtbare Anzeige: die Augen
# erscheinen nur im Bildschirmschoner, und der verlangt SCREENSAVER_AFTER_SECONDS
# (30 s) ohne Eingabe — während `alert` 0,8 s nach einer Drehung und `action`
# 2,5 s nach einer Aktion gilt. Die Bedingungen schliessen sich aus, beide
# Zustände zeigen deshalb den Textschirm mit dem ASCII-Gesicht. Die Einträge
# stehen trotzdem hier: sie sind die Antwort auf die Frage "und wenn doch",
# und `test_alert_und_action_sind_im_schoner_unerreichbar` schlägt an, falls
# jemand eine der drei Zeitkonstanten so verschiebt, dass sie erreichbar werden.
EYE_MOODS: dict[str, tuple[str, float, bool]] = {
    "thriving": ("happy", 1.00, False),
    "content": ("default", 1.00, False),
    "struggling": ("tired", 1.00, False),
    "dormant": ("default", 0.12, False),  # Schlitz — das Pet schläft
    "alert": ("default", 1.20, True),  # weit offen, folgt dem Drehknopf
    "action": ("default", 0.55, False),  # zusammengekniffen, konzentriert
}

# Zeitfenster des Verlaufs-Schirms, im Wechsel gezeigt. Die Namen sind die des
# Endpunkts `/agents/{id}/balance-history`; die Beschriftung steht daneben.
HISTORY_WINDOWS: tuple[tuple[str, str], ...] = (("24h", "24 STD"), ("7d", "7 TAGE"))
HISTORY_SWITCH_SECONDS = 6.0  # wie lange ein Fenster stehen bleibt
HISTORY_POLL_SECONDS = 300  # der Verlauf aendert sich langsam — alle 5 min genuegt

COMPASS_PRESETS = ("attack", "defend", "grow", "trade", "explore")

# --- Evolution constants (mirror server: backend/app/core/entity_tiers.py) --
# Pet zeigt "Evolve" nur wenn ALLE Server-Checks tatsächlich grün wären.
# Ohne diesen Mirror landeten zwei Klicks im "Evolve"-Menü oft im 400-Reject
# oder zogen 1000 E ab obwohl das Label "~500 E" sagte (S157 Forensik
# Comet-hand-Field). Server-Tabellen müssen synchron gepflegt werden — bei
# Änderung in entity_tiers.py: hier nachziehen.
EVOLUTION_ENERGY_COST: dict[int, int] = {
    1: 1_000,  # T1 → T2
    2: 5_000,  # T2 → T3
    3: 25_000,  # T3 → T4
    4: 100_000,  # T4 → T5
}
REIFE_THRESHOLDS: dict[int, int] = {
    2: 100,  # next_tier=2 needs reife >= 100
    3: 500,
    4: 2_000,
    5: 10_000,
}
TIER_REQUIRED_TYPE: dict[int, str] = {
    2: "oscillator",
    3: "spaceship",
    4: "gun",
    5: "breeder",
}


@dataclass
class PetState:
    """Everything UI + input thread need to share. The single source of truth."""

    current_screen: int = 0  # 0..7
    menu_open: bool = False
    menu_index: int = 0
    compass_submenu: bool = False
    compass_index: int = 0
    paused: bool = False

    last_rotation_at: float = 0.0
    last_action_at: float = 0.0
    last_action_label: str = ""

    # Poll-event timestamps for screensaver eye-blinks
    # (state -> left eye, events -> right eye, decisions -> both squint).
    last_state_poll_at: float = 0.0
    last_events_poll_at: float = 0.0
    last_decisions_poll_at: float = 0.0

    # populated by the poller
    game_state: GameState | None = None
    events: list[dict] = field(default_factory=list)
    last_decision: dict | None = None

    # S157: User-getriggerte Aktion (Encoder-Klick) und ihr Server-Outcome.
    # Vor S157 schluckte _execute_action Erfolge stillschweigend, der Pet zeigte
    # nur einen 1-Sek Face-Mood-Wechsel. Bei Comet-hand verschwanden 2x 1000 E
    # ohne sichtbares Pet-Feedback. Screen 7 (Last Action) zeigt jetzt User-
    # Aktionen parallel zu Server-LLM-Decisions.
    # Schema: {"action": str, "status": "ok"|"fail"|"skipped", "detail": str, "ts": float}
    last_user_action: dict | None = None
    connection_ok: bool = False
    last_error: str = ""

    # Energie-Verlauf je Zeitfenster, fertig zum Zeichnen (nur die Werte —
    # die Zeitstempel braucht die Anzeige nicht, sie spannt ueber die Breite).
    balance_history: dict[str, list[float]] = field(default_factory=dict)
    last_history_poll_at: float = 0.0


# ----------------------------------------------------------------------------
# Mood logic (pure function: state → face)
# ----------------------------------------------------------------------------


def mood_from_state(ps: PetState, now: float) -> str:
    """Pick the face from the current state.

    Order prioritises visual feedback: ongoing action > encoder rotation >
    sleep > distress > normal.
    """
    if now - ps.last_action_at < ACTION_FLASH_SECONDS:
        return "action"
    if now - ps.last_rotation_at < ALERT_AFTER_ROTATION_SECONDS:
        return "alert"

    state = ps.game_state
    if state is None:
        return "content"  # no state yet — show a neutral face

    # Dormant: no decision in the last DORMANT_AFTER_HOURS
    decision = ps.last_decision
    if decision and decision.get("created_at"):
        age_hours = _age_hours(decision["created_at"], now)
        if age_hours is not None and age_hours > DORMANT_AFTER_HOURS:
            return "dormant"

    situation = state.world_briefing.situation if state.world_briefing else None
    trend = situation.energy_trend if situation else "stable"

    if situation and situation.active_catastrophe:
        return "struggling"
    if situation and situation.fields_owned == 0:
        return "struggling"
    if trend == "falling":
        return "struggling"
    if trend == "rising":
        return "thriving"
    return "content"


def apply_blink(face: str, ps: PetState, now: float) -> str:
    """Overlay a 300 ms blink on the screensaver face when a backend poll fires.

    Priority (decisions > events > state) so a rare decision-poll always wins
    over the more frequent state/events polls. The face is assumed to be in
    the canonical 8-char shape '( X__X )' with the eyes at positions 2 and 5.
    """
    if (now - ps.last_decisions_poll_at) < SCREENSAVER_BLINK_DURATION:
        return "( >__< )"
    if (now - ps.last_events_poll_at) < SCREENSAVER_BLINK_DURATION:
        # right eye (position 5) wide
        return face[:5] + "o" + face[6:]
    if (now - ps.last_state_poll_at) < SCREENSAVER_BLINK_DURATION:
        # left eye (position 2) wide
        return face[:2] + "o" + face[3:]
    return face


def poll_just_fired(ps: PetState, now: float) -> bool:
    """True kurz nach einer Backend-Abfrage — der Anlass zum Blinzeln.

    Grafische Entsprechung zu `apply_blink`, das dasselbe Ereignis für die
    Terminal-Darstellung in ein anderes ASCII-Gesicht übersetzt. Auf dem
    Display blinzelt das Pet stattdessen: es holt Daten, also schlägt es kurz
    die Augen zu. Ohne diese Kopplung wäre der Autoblinker reine Dekoration —
    so zeigt das Gesicht tatsächlich etwas an.
    """
    letzte = max(ps.last_decisions_poll_at, ps.last_events_poll_at, ps.last_state_poll_at)
    return 0.0 <= (now - letzte) < SCREENSAVER_BLINK_DURATION


def total_active_cells(ps: PetState) -> int:
    """Sum of active cells across all owned fields, 0 if no state."""
    if not ps.game_state:
        return 0
    return sum(f.active_cell_count for f in ps.game_state.fields)


def _age_hours(iso_timestamp: str, now: float) -> float | None:
    """Age in hours; returns None if the timestamp can't be parsed."""
    try:
        from datetime import datetime, timezone

        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        return (now - dt.replace(tzinfo=timezone.utc).timestamp()) / 3600.0
    except Exception:
        return None


# ----------------------------------------------------------------------------
# Contextual action menu
# ----------------------------------------------------------------------------


def _find_evolvable_field(state: GameState, energy: float) -> Any | None:
    """First owned field that meets ALL server-side evolve criteria.

    Mirrors backend/app/api/v1/endpoints/agent_game.py:_handle_evolve checks:
    - entity_tier > 0 and < 5
    - reife_score >= REIFE_THRESHOLDS[next_tier]
    - entity_type matches TIER_REQUIRED_TYPE[next_tier]
    - energy >= EVOLUTION_ENERGY_COST[entity_tier]

    Returns first matching field or None. Pet zeigt "Evolve" nur wenn
    ein Server-Call tats\u00e4chlich erfolgreich w\u00e4re.
    """
    for f in state.fields:
        tier = f.entity_tier or 0
        if tier <= 0 or tier >= 5:
            continue
        next_tier = tier + 1
        if (f.reife_score or 0) < REIFE_THRESHOLDS.get(next_tier, 999_999):
            continue
        required_type = TIER_REQUIRED_TYPE.get(next_tier)
        if required_type and f.entity_type != required_type:
            continue
        cost = EVOLUTION_ENERGY_COST.get(tier, 0)
        if energy < cost:
            continue
        return f
    return None


def build_menu(state: GameState | None, paused: bool) -> list[tuple[str, str]]:
    """Menu entries derived from the agent's current situation.

    Returns a list of (label, action_key). The action_key is interpreted by
    execute_menu_action (an API call or a pseudo-action like "compass"/"pause").
    """
    items: list[tuple[str, str]] = []

    if state is None:
        items.append(("Wait for state...", "noop"))
        items.append(("Pause" if not paused else "Resume", "pause"))
        return items

    situation = state.world_briefing.situation if state.world_briefing else None
    energy = state.energy

    if situation:
        if situation.fields_owned == 0:
            items.append(("Create Field (100 E)", "create_field"))
        if situation.fields_without_cells > 0 and situation.affordable_presets:
            # affordable_presets is typically sorted cheapest-first
            preset = situation.affordable_presets[0]
            items.append((f"Place Cells ({preset})", f"place_cells:{preset}"))
        # Evolve: nur wenn echtes Field die Kriterien erf\u00fcllt (S157-Fix).
        # Vor S157 nutzte das Men\u00fc `state.ranking.player_tier` (Novice/Bronze/...)
        # und _tier_up_cost = 500 * 2^(tier-1) \u2014 falsche Tier-Variable und
        # falsche Magnitude. User sah "Evolve (~500 E)", Server zog 1000 E ab.
        evolvable = _find_evolvable_field(state, energy)
        if evolvable is not None:
            cost = EVOLUTION_ENERGY_COST[evolvable.entity_tier]
            label = f"Evolve T{evolvable.entity_tier}->T{evolvable.entity_tier + 1} ({cost} E)"
            items.append((label, "evolve"))
        if situation.active_catastrophe:
            items.append(("Buy Shield", "buy_shield"))

    items.append(("Set Compass \u25b6", "compass"))
    items.append(("Pause" if not paused else "Resume", "pause"))
    items.append(("Close Menu", "close"))
    return items


# ----------------------------------------------------------------------------
# Screen renderers (return a list of lines; the display layer handles layout)
# ----------------------------------------------------------------------------


def render_screen(ps: PetState, now: float) -> list[str]:
    """Render the active screen as text lines (7 lines, ~21 chars each).

    If the menu is open, the menu is drawn in place of screen 1.
    """
    if ps.menu_open and ps.current_screen == 0:
        return _render_menu(ps)
    screen = ps.current_screen
    renderers = [
        _render_face,
        _render_energy,
        _render_territory,
        _render_events,
        _render_benchmark,
        _render_journal,
        _render_last_action,
        _render_rules,
    ]
    title = [
        "Face",
        "Energy",
        "Territory",
        "Events",
        "Benchmark",
        "Journal",
        "Last Action",
        "Rules",
    ][screen]
    header = f"[{screen + 1}/8] {title}"
    body = renderers[screen](ps, now)
    if ps.paused:
        header = f"PAUSED  {header}"
    if not ps.connection_ok and ps.last_error:
        body = [*body, f"! {ps.last_error[:20]}"]
    return [header, "-" * 21, *body]


def _render_face(ps: PetState, now: float) -> list[str]:
    mood = mood_from_state(ps, now)
    face = FACES[mood]
    state = ps.game_state
    energy_str = f"{int(state.energy)} E" if state else "--"
    name = state.agent_name if state and state.agent_name else "agent"
    headline = _headline_for(state) if state else ""
    # 5 body lines + header + separator = 7 total. Some SH1106 1.3" modules
    # crop the last 1-2 px on the y-axis; rendering 8 lines at 8 px each
    # leaves no margin and the bottom line gets clipped. Reported as a
    # build feedback in S156.
    return [
        face.center(21),
        mood.center(21),
        "",
        f"{name[:14]:14s} {energy_str:>6}",
        headline[:21],
    ]


def _headline_for(state: GameState) -> str:
    """A snappy one-liner from the WorldBriefing for the face screen."""
    wb = state.world_briefing
    if not wb:
        return ""
    if wb.last_event:
        return f"Event: {wb.last_event[:14]}"
    s = wb.situation
    if s.active_catastrophe:
        return f"! {s.active_catastrophe[:17]}"
    if s.fields_owned == 0:
        return "No fields yet"
    return f"{s.fields_owned} fields, {wb.total_agents} agents"


def _render_energy(ps: PetState, now: float) -> list[str]:
    state = ps.game_state
    if not state:
        return ["", "No state yet..."]
    rank = state.world_briefing.your_rank if state.world_briefing else 0
    total = state.world_briefing.total_agents if state.world_briefing else 0
    trend = state.world_briefing.situation.energy_trend if state.world_briefing else "stable"
    trend_arrow = {"rising": "up", "falling": "down", "stable": "stable"}.get(trend, trend)
    return [
        f"Energy: {int(state.energy)} E",
        f"Trend:  {trend_arrow}",
        "",
        f"Tier:   {state.ranking.player_tier} {state.ranking.tier_name[:12]}",
        f"Rank:   {rank}/{total}" if total else "Rank:   -",
    ]


def _render_territory(ps: PetState, now: float) -> list[str]:
    state = ps.game_state
    if not state:
        return ["", "No state yet..."]
    total_cells = sum(f.active_cell_count for f in state.fields)
    cubes = len(state.cubes)
    sit = state.world_briefing.situation if state.world_briefing else None
    spores = sit.dormant_spores_on_fields if sit else 0
    return [
        f"Fields:  {len(state.fields)}",
        f"Cubes:   {cubes}",
        f"Cells:   {total_cells}",
        f"Spores:  {spores}",
        f"Compass: {state.compass_preset or 'unset'}",
    ]


def _render_events(ps: PetState, now: float) -> list[str]:
    if not ps.events:
        return ["", "No recent events."]
    out = []
    for ev in ps.events[:5]:
        typ = ev.get("event_type", "?")[:12]
        tick = ev.get("tick", "?")
        out.append(f"t{tick} {typ}")
    return out


def _render_benchmark(ps: PetState, now: float) -> list[str]:
    state = ps.game_state
    if not state or not state.world_briefing:
        return ["", "No state yet..."]
    sit = state.world_briefing.situation
    if sit.benchmark_ready:
        return [
            "",
            "Benchmark ready!",
            "",
            "See report at",
            "cosmergon.com",
        ]
    return [
        "Days to benchmark:",
        "",
        f"  {sit.benchmark_days_remaining}",
        "",
        "(7-day report)",
    ]


def _render_journal(ps: PetState, now: float) -> list[str]:
    decision = ps.last_decision
    if not decision:
        return ["", "No decisions yet."]
    journal = decision.get("journal") or decision.get("reasoning") or ""
    return _wrap(journal, width=21, max_lines=5)


def _render_last_action(ps: PetState, now: float) -> list[str]:
    """Show last user-clicked action AND last LLM-decision (S157 M2).

    Pre-S157 zeigte dieser Screen nur LLM-Decisions aus /decisions. Bei
    agent_mode=api (typisch fürs Pet) gibt es keine LLM-Decisions → Screen
    war leer trotz aktiver User-Klicks. Comet-hand sah 2× 1000 E verschwinden
    ohne irgendeinen Pet-Feedback.

    Layout (max 5 Body-Zeilen auf 128x64 OLED):
        You ok evolve         (User-Action mit Status-Marker)
            -1000E free       (Detail aus _summarize_user_action)
        ---
        LLM: action outcome   (LLM-Decision falls vorhanden)
        reasoning lines...
    """
    user = ps.last_user_action
    decision = ps.last_decision

    if not user and not decision:
        return ["", "No actions yet."]

    lines: list[str] = []
    if user:
        marker = {"ok": "OK", "fail": "!!", "skipped": ".."}.get(user.get("status", ""), "??")
        lines.append(f"You {marker} {user.get('action', '?')[:12]}")
        detail = user.get("detail") or ""
        if detail:
            lines.append(f"    {detail[:17]}")
    if decision:
        if user:
            lines.append("---")
            action = decision.get("action", "?")
            outcome = decision.get("outcome", "?")
            lines.append(f"LLM:{action[:7]} {outcome[:7]}")
        else:
            action = decision.get("action", "?")
            outcome = decision.get("outcome", "?")
            reasoning = decision.get("reasoning", "")
            lines.append(f"Action:  {action[:12]}")
            lines.append(f"Result:  {outcome[:12]}")
            lines.extend(_wrap(reasoning, width=21, max_lines=2))
    return lines[:5]


def _render_rules(ps: PetState, now: float) -> list[str]:
    state = ps.game_state
    if not state or not state.learned_rules:
        return ["", "No rules yet.", "", "(updated every", " 100 ticks)"]
    out = []
    for rule in state.learned_rules[:5]:
        out.extend(_wrap(rule, width=21, max_lines=1))
    return out


def _render_menu(ps: PetState) -> list[str]:
    """Action menu drawn on top of the face screen."""
    if ps.compass_submenu:
        header = "COMPASS"
        items = [(p, p) for p in COMPASS_PRESETS] + [("back", "back")]
        idx = ps.compass_index
    else:
        header = "ACTIONS"
        items = build_menu(ps.game_state, ps.paused)
        idx = ps.menu_index

    lines = [header, "-" * 21]
    # Window around the current index (max 5 entries visible)
    start = max(0, min(idx - 2, len(items) - 5))
    end = min(len(items), start + 5)
    for i in range(start, end):
        label = items[i][0]
        marker = ">" if i == idx else " "
        lines.append(f"{marker} {label[:19]}")
    return lines


def _wrap(text: str, width: int = 21, max_lines: int = 6) -> list[str]:
    """Simple greedy word-boundary wrapping."""
    if not text:
        return [""]
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        if len(cur) + 1 + len(w) <= width:
            cur = f"{cur} {w}".strip()
        else:
            if cur:
                lines.append(cur)
            cur = w[:width]
        if len(lines) >= max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines[:max_lines]


# ----------------------------------------------------------------------------
# Display backends (OLED via luma.oled + simulation via stdout)
# ----------------------------------------------------------------------------


class StdoutDisplay:
    """Simulation display — writes each frame to the console (laptop dev)."""

    def __init__(self) -> None:
        self._last_frame: str = ""

    def draw(self, lines: list[str]) -> None:
        frame = "\n".join(lines)
        if frame != self._last_frame:
            os.system("clear" if os.name != "nt" else "cls")
            print("+" + "-" * 23 + "+")
            for line in lines:
                print(f"| {line[:21]:21s} |")
            for _ in range(max(0, 8 - len(lines))):
                print("| " + " " * 21 + " |")
            print("+" + "-" * 23 + "+")
            self._last_frame = frame

    def draw_big_face(self, face: str, cell_count: int = 0) -> None:
        """Screensaver mode in the terminal — print the face plus cell dots.

        Bekommt weiterhin das fertige ASCII-Gesicht: im Terminal gibt es keine
        Pixel, dort bleibt `( ^__^ )` die Darstellung. Das OLED bekommt an
        derselben Stelle den ZUSTAND und zeichnet daraus animierte Augen.
        """
        dots = "." * min(cell_count, 30)
        frame = f"BIG: {face} cells={cell_count}"
        if frame != self._last_frame:
            os.system("clear" if os.name != "nt" else "cls")
            print()
            print()
            print(f"          {face}".center(23))
            print()
            print(dots.center(23))
            print()
            self._last_frame = frame

    def close(self) -> None:
        pass


class OledDisplay:
    """Hardware display — SH1106 128x64 over I2C (luma.oled)."""

    def __init__(self) -> None:
        from luma.core.interface.serial import i2c
        from luma.oled.device import sh1106
        from PIL import ImageFont

        from .robo_eyes import RoboEyes

        self._serial = i2c(port=1, address=0x3C)
        self._device = sh1106(self._serial, rotate=0)
        # Default font (8 px) fits 21 chars × 8 lines on a 128×64 panel.
        self._font = ImageFont.load_default()
        # Big monospace font for the screensaver — adaptive: starts at
        # SCREENSAVER_FONT_MAX_SIZE and shrinks until '( ^__^ )' (the
        # widest face string) fits in DISPLAY_WIDTH_PX with a small margin.
        # Seit dem Umstieg auf gezeichnete Augen nur noch für Geräte ohne
        # PIL-Zeichenpfad relevant — bleibt als Rückfallebene bestehen.
        self._big_font = self._pick_big_font(ImageFont)

        # Animierte Augen für den Screensaver. Das Objekt lebt so lange wie das
        # Display, denn es TRÄGT den Animationszustand (Lidstellung, Blickziel,
        # nächster Blinzler). Pro Bild neu erzeugt gäbe es keine Bewegung.
        self._eyes = RoboEyes(
            screen_width=DISPLAY_WIDTH_PX,
            screen_height=DISPLAY_HEIGHT_PX,
            autoblinker=True,
            blink_interval=4.0,
            blink_variation=3.0,
            idle=True,
            idle_interval=3.5,
            idle_variation=2.5,
        )
        self._eye_height_base = self._eyes.eye_height
        self._last_eye_frame: bytes | None = None

    @staticmethod
    def _pick_big_font(image_font_module) -> Any:
        """Pick the largest font where '( ^__^ )' fits the display width.

        Tries TrueType paths first (crisp at any size), falls back to the
        Pillow Bitmap default with the load_default(size=N) signature
        (Pillow 10+), and finally to the 8 px default if everything else
        fails on this host.
        """
        sample = "( ^__^ )"
        max_width = DISPLAY_WIDTH_PX - 4  # 2 px safety on each side

        def _fits(font: Any) -> bool:
            if hasattr(font, "getbbox"):
                bbox = font.getbbox(sample)
                return (bbox[2] - bbox[0]) <= max_width
            # Pre-9.2 Pillow: getsize was the public API
            if hasattr(font, "getsize"):
                return font.getsize(sample)[0] <= max_width
            return True  # can't measure — assume it fits and hope

        for path in SCREENSAVER_FONT_PATHS:
            for size in range(SCREENSAVER_FONT_MAX_SIZE, SCREENSAVER_FONT_MIN_SIZE - 1, -1):
                try:
                    font = image_font_module.truetype(path, size)
                except OSError:
                    break  # this path doesn't exist — try the next
                if _fits(font):
                    return font

        # No TrueType worked — try Pillow 10+ Bitmap default with size kwarg.
        for size in range(SCREENSAVER_FONT_MAX_SIZE, SCREENSAVER_FONT_MIN_SIZE - 1, -1):
            try:
                font = image_font_module.load_default(size=size)
            except (TypeError, AttributeError):
                break  # Pillow < 10 — load_default has no size kwarg
            if _fits(font):
                return font

        return image_font_module.load_default()

    def draw(self, lines: list[str]) -> None:
        from luma.core.render import canvas

        # 7 lines × 8 px + 4 px top margin = 60 px on a 64 px display.
        # Some SH1106 1.3" modules crop the last 1-2 px on the y-axis
        # (and the default PIL font on Pillow 11+ is taller than 8 px).
        # Rendering only 7 lines with a top margin gives us a safe
        # bottom buffer everywhere. Build feedback S156 (v0.1.5).
        with canvas(self._device) as draw:
            for i, line in enumerate(lines[:7]):
                draw.text((0, 4 + i * 8), line[:21], font=self._font, fill="white")

    def draw_eyes(self, mood: str, now: float, blink: bool = False) -> None:
        """Screensaver: animierte Augen über die volle Fläche.

        Ersetzt das ASCII-Gesicht samt Zell-Leiste am unteren Rand (Gründer,
        22.08.2026: „die unteren 4 px für die Zell-Leiste verwerfen wir und
        nutzen die ganze Fläche für das Gesicht").

        Übertragen wird nur, wenn sich das Bild tatsächlich geändert hat. Der
        Vergleich kostet 1 kB Speicher und einen Bytevergleich, spart aber die
        I2C-Übertragung — die mit 32,7 ms das Teuerste im ganzen Ablauf ist
        (Bildaufbau: 0,38 ms). Ein ruhendes Gesicht ändert sich in etwa einem
        Drittel der Bilder, der Rest wäre reine Buslast.
        """
        stimmung, hoehe, neugier = EYE_MOODS.get(mood, EYE_MOODS["content"])
        self._eyes.set_mood(stimmung)
        self._eyes.eye_height = max(2, int(self._eye_height_base * hoehe))
        self._eyes.curiosity = neugier
        if blink:
            self._eyes.blink(now)

        bild = self._eyes.render(now)
        roh = bild.tobytes()
        if roh == self._last_eye_frame:
            return
        self._last_eye_frame = roh
        self._device.display(bild)

    def draw_verlauf(self, name: str, werte: list[float], label: str, konto: float) -> None:
        """Verlaufs-Schirm: Kurve mit gefüllter Fläche, Name des Agenten unten.

        Aufteilung der 64 px (Gründer-Vorgabe 22.08.2026: „unten der name des
        agenten, darüber der verlauf des energie-kontos als kurve … mit
        angelegter fläche drunter"):

            0–9    Kopfzeile: Zeitfenster links, Kontostand rechts
            10–51  die Fläche
            52–63  Name des Agenten

        Ohne Daten bleibt die Fläche leer und es steht ein Hinweis dort — eine
        leere Fläche allein sähe aus wie ein Konto auf null.
        """
        from luma.core.render import canvas

        from .sparkline import flaeche_zeichnen, kurz

        with canvas(self._device) as draw:
            draw.text((0, 0), label, font=self._font, fill="white")
            stand = kurz(konto)
            draw.text((DISPLAY_WIDTH_PX - 6 * len(stand), 0), stand, font=self._font, fill="white")
            if len(werte) >= 2:
                # 2 px Luft unter der Kopfzeile: ohne sie stösst die Fläche im
                # Hochpunkt an die Schrift und sieht abgeschnitten aus.
                flaeche_zeichnen(draw, werte, 0, 12, DISPLAY_WIDTH_PX - 1, 39)
            else:
                draw.text((18, 26), "kein Verlauf", font=self._font, fill="white")
            draw.text((0, 53), name[:21], font=self._font, fill="white")

    def close(self) -> None:
        self._device.cleanup()


def make_display(simulate: bool) -> Any:
    if simulate:
        return StdoutDisplay()
    try:
        return OledDisplay()
    except Exception as err:
        logger.warning("OLED unavailable (%s) — falling back to simulation.", err)
        return StdoutDisplay()


# ----------------------------------------------------------------------------
# Input-Backends (KY-040 via rpi-lgpio / RPi.GPIO + Keyboard-Simulation)
# ----------------------------------------------------------------------------


class InputEvent:
    ROT_LEFT = "left"
    ROT_RIGHT = "right"
    CLICK = "click"
    LONGPRESS = "longpress"


class GpioEncoder:
    """KY-040 on CLK/DT/SW — events land in an asyncio.Queue (thread-safe)."""

    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop) -> None:
        import RPi.GPIO as GPIO  # type: ignore[import-not-found]

        self._GPIO = GPIO
        self._queue = queue
        self._loop = loop
        self._press_start: float | None = None

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(ENC_CLK, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(ENC_DT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(ENC_SW, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        self._last_clk = GPIO.input(ENC_CLK)
        GPIO.add_event_detect(ENC_CLK, GPIO.BOTH, callback=self._on_rotate, bouncetime=2)
        GPIO.add_event_detect(ENC_SW, GPIO.BOTH, callback=self._on_switch, bouncetime=20)

    def _push(self, event: str) -> None:
        """Thread-safely push an event onto the asyncio queue."""
        self._loop.call_soon_threadsafe(self._queue.put_nowait, event)

    def _on_rotate(self, _channel: int) -> None:
        clk = self._GPIO.input(ENC_CLK)
        dt = self._GPIO.input(ENC_DT)
        if clk != self._last_clk:
            if dt != clk:
                self._push(InputEvent.ROT_RIGHT)
            else:
                self._push(InputEvent.ROT_LEFT)
        self._last_clk = clk

    def _on_switch(self, _channel: int) -> None:
        pressed = self._GPIO.input(ENC_SW) == 0
        now = time.monotonic()
        if pressed:
            self._press_start = now
        else:
            if self._press_start is None:
                return
            duration = now - self._press_start
            self._press_start = None
            if duration >= LONGPRESS_SECONDS:
                self._push(InputEvent.LONGPRESS)
            elif duration >= 0.03:  # debounce minimum
                self._push(InputEvent.CLICK)

    def close(self) -> None:
        try:
            self._GPIO.cleanup()
        except Exception:
            pass


class KeyboardEncoder:
    """Simulation input for laptop dev: arrow keys + Enter.

    Uses stdin in raw mode — Unix terminals only.
    """

    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop) -> None:
        import termios
        import tty

        self._queue = queue
        self._loop = loop
        self._fd = sys.stdin.fileno()
        self._stop = False
        self._old_settings = None
        try:
            self._old_settings = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
            self._task = loop.create_task(self._reader())
        except (termios.error, OSError):
            # No TTY (e.g. unit test, pipe) — skip the reader; the display
            # still runs, just without input.
            logger.info("KeyboardEncoder: stdin is not a TTY, input disabled.")
            self._task = None

    async def _reader(self) -> None:
        loop = asyncio.get_running_loop()
        while not self._stop:
            ch = await loop.run_in_executor(None, sys.stdin.read, 1)
            if ch == "\x1b":
                seq = await loop.run_in_executor(None, sys.stdin.read, 2)
                if seq == "[C":
                    await self._queue.put(InputEvent.ROT_RIGHT)
                elif seq == "[D":
                    await self._queue.put(InputEvent.ROT_LEFT)
            elif ch in ("\r", "\n"):
                await self._queue.put(InputEvent.CLICK)
            elif ch == " ":
                await self._queue.put(InputEvent.LONGPRESS)
            elif ch == "q":
                os.kill(os.getpid(), signal.SIGINT)

    def close(self) -> None:
        import termios

        self._stop = True
        if self._old_settings is not None:
            try:
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)
            except Exception:
                pass


def make_encoder(simulate: bool, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop) -> Any:
    if simulate:
        return KeyboardEncoder(queue, loop)
    try:
        return GpioEncoder(queue, loop)
    except Exception as err:
        logger.warning("GPIO unavailable (%s) — falling back to keyboard.", err)
        return KeyboardEncoder(queue, loop)


# ----------------------------------------------------------------------------
# Input handling (navigation + menu execution)
# ----------------------------------------------------------------------------


async def handle_event(event: str, ps: PetState, agent: CosmergonAgent, now: float) -> None:
    if event in (InputEvent.ROT_LEFT, InputEvent.ROT_RIGHT):
        ps.last_rotation_at = now
        _handle_rotate(event, ps)
    elif event == InputEvent.CLICK:
        await _handle_click(ps, agent, now)
    elif event == InputEvent.LONGPRESS:
        await _handle_longpress(ps, agent)


def _handle_rotate(event: str, ps: PetState) -> None:
    direction = 1 if event == InputEvent.ROT_RIGHT else -1
    if ps.menu_open:
        if ps.compass_submenu:
            n = len(COMPASS_PRESETS) + 1  # +1 for "back"
            ps.compass_index = (ps.compass_index + direction) % n
        else:
            items = build_menu(ps.game_state, ps.paused)
            ps.menu_index = (ps.menu_index + direction) % len(items)
    else:
        ps.current_screen = (ps.current_screen + direction) % 8


async def _handle_click(ps: PetState, agent: CosmergonAgent, now: float) -> None:
    if not ps.menu_open:
        if ps.current_screen == 0:
            ps.menu_open = True
            ps.menu_index = 0
        else:
            # Short click on other screens jumps back to screen 1
            ps.current_screen = 0
        return

    if ps.compass_submenu:
        items = [*list(COMPASS_PRESETS), "back"]
        choice = items[ps.compass_index]
        if choice == "back":
            ps.compass_submenu = False
            return
        await _execute_action(f"compass:{choice}", ps, agent, now)
        ps.compass_submenu = False
        ps.menu_open = False
        return

    items = build_menu(ps.game_state, ps.paused)
    label, action_key = items[ps.menu_index]

    if action_key == "compass":
        ps.compass_submenu = True
        ps.compass_index = 0
        return
    if action_key == "close":
        ps.menu_open = False
        return
    if action_key == "noop":
        return

    await _execute_action(action_key, ps, agent, now)
    ps.last_action_label = label
    ps.menu_open = False


async def _handle_longpress(ps: PetState, agent: CosmergonAgent) -> None:
    if ps.menu_open:
        # Back out of the menu
        if ps.compass_submenu:
            ps.compass_submenu = False
        else:
            ps.menu_open = False
        return
    ps.paused = not ps.paused


def _summarize_user_action(label: str, result: Any | None, now: float) -> dict:
    """Build a Pet-display summary of an executed user action (S157 M2).

    Pre-S157 schluckte _execute_action Erfolge stillschweigend, Pet zeigte nur
    1 s Face-Mood-Wechsel. Bei Comet-hand verschwanden 2× 1000 E ohne Feedback.

    Schema: {"action": str, "status": "ok"|"fail"|"skipped", "detail": str, "ts": float}
    """
    rec: dict = {"action": label, "ts": now}
    if result is None:
        rec["status"] = "skipped"
        rec["detail"] = ""
        return rec
    if getattr(result, "success", False):
        rec["status"] = "ok"
        data = getattr(result, "data", None) or {}
        # Häufige Felder: evolve, place_cells, create_field
        if "energy_cost" in data:
            ec = data.get("energy_cost", 0)
            free = data.get("free_re_evolution", False)
            rec["detail"] = f"-{int(ec)}E" + (" free" if free else "")
        elif "new_tier" in data:
            rec["detail"] = f"->T{data['new_tier']}"
        else:
            rec["detail"] = "ok"
    else:
        rec["status"] = "fail"
        msg = getattr(result, "error_message", "") or "?"
        rec["detail"] = msg[:18]
    return rec


async def _execute_action(action_key: str, ps: PetState, agent: CosmergonAgent, now: float) -> None:
    """Execute a menu action. Outcome wird auf ps.last_user_action geschrieben (S157 M2)."""
    state = ps.game_state
    label = action_key.split(":", 1)[0]
    result: Any | None = None
    try:
        if action_key == "create_field" and state and state.universe_cubes:
            cube_id = state.universe_cubes[0].id
            result = await agent.act("create_field", cube_id=cube_id)
        elif action_key.startswith("place_cells:") and state and state.fields:
            preset = action_key.split(":", 1)[1]
            empty_field = next((f for f in state.fields if f.active_cell_count == 0), None)
            if empty_field:
                result = await agent.act("place_cells", field_id=empty_field.id, preset=preset)
        elif action_key == "evolve" and state and state.fields:
            # S157: Evolve auf das tatsächlich-evolvable Field, nicht blind auf
            # state.fields[0]. Pre-S157 wäre der Server-Call oft mit 400 not_mature
            # oder pattern_type_mismatch zurückgekommen, wenn das erste Field
            # nicht passte aber ein anderes Field schon.
            target = _find_evolvable_field(state, state.energy)
            if target is not None:
                result = await agent.act("evolve", field_id=target.id)
        elif action_key == "buy_shield" and state and state.fields:
            result = await agent.act("buy_shield", field_id=state.fields[0].id)
        elif action_key == "pause":
            ps.paused = not ps.paused
            ps.last_user_action = {
                "action": "pause",
                "status": "ok",
                "detail": "paused" if ps.paused else "resumed",
                "ts": now,
            }
            ps.last_action_at = now
            return
        elif action_key.startswith("compass:"):
            preset = action_key.split(":", 1)[1]
            await agent.set_compass(preset)
            ps.last_user_action = {
                "action": "compass",
                "status": "ok",
                "detail": preset,
                "ts": now,
            }
            ps.last_action_at = now
            return
        ps.last_user_action = _summarize_user_action(label, result, now)
        ps.last_action_at = now
    except Exception as err:
        ps.last_user_action = {
            "action": label,
            "status": "fail",
            "detail": str(err)[:18],
            "ts": now,
        }
        ps.last_error = f"action: {err}"[:30]
        logger.exception("Action %s failed", action_key)


# ----------------------------------------------------------------------------
# Main loop (state + display + input)
# ----------------------------------------------------------------------------


async def run_pet(
    agent: CosmergonAgent,
    simulate: bool,
    llm_provider: Any | None = None,
    llm_interval_s: float = 60.0,
    tree_decider: Any | None = None,
    tree_interval_s: float = 60.0,
) -> None:
    # Validate decider-backend selection BEFORE opening the agent — keeps the
    # error message clean and avoids partial init.
    if llm_provider is not None and tree_decider is not None:
        raise ValueError("run_pet: `llm_provider` and `tree_decider` are mutually exclusive.")
    # `async with agent` opens the SDK's HTTP client. Without this, every
    # `_request()` call raises "Agent not connected. Call run() or use async
    # with." — which surfaces on the Pet's display as `! state: Agent not co`
    # on every info screen. Reported on cosmergon-pet#1.
    async with agent:
        ps = PetState()
        display = make_display(simulate)
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        encoder = make_encoder(simulate, queue, loop)

        stop = asyncio.Event()

        def _stop_handler(*_: Any) -> None:
            stop.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _stop_handler)

        # Initial registration / state fetch
        await _prime_state(agent, ps)

        # Background tasks: periodic polls
        poll_state_task = asyncio.create_task(_poll_state(agent, ps, stop))
        poll_events_task = asyncio.create_task(_poll_events(agent, ps, stop))
        poll_decisions_task = asyncio.create_task(_poll_decisions(agent, ps, stop))
        history_task = asyncio.create_task(_history_loop(agent, ps, stop))
        draw_task = asyncio.create_task(_draw_loop(display, ps, stop))

        # Optional autonomous decision loop. Runs alongside button-driven
        # actions; user can still press the encoder for manual moves. Two
        # backends, mutually exclusive (caller picks one):
        #   - `llm_provider` → ``llm_decision_loop`` (Ollama/OpenAI/...)
        #   - `tree_decider` → ``tree_decision_loop`` (rule-based, no LLM)
        llm_task: asyncio.Task | None = None
        tree_task: asyncio.Task | None = None
        if llm_provider is not None:
            from .llm_decider import llm_decision_loop

            def _on_llm_decision(action: str, params: dict, elapsed: float, success: bool) -> None:
                ps.last_user_action = {
                    "action": f"llm:{action}",
                    "status": "ok" if success else "fail",
                    "detail": f"{elapsed:.1f}s",
                    "ts": time.monotonic(),
                }
                ps.last_action_at = time.monotonic()
                ps.last_action_label = f"llm {action}"

            llm_task = asyncio.create_task(
                llm_decision_loop(
                    agent,
                    llm_provider,
                    interval_s=llm_interval_s,
                    stop=stop,
                    on_decision=_on_llm_decision,
                )
            )
        elif tree_decider is not None:
            from .tree_loop import tree_decision_loop

            def _on_tree_decision(action: str, params: dict, elapsed: float, success: bool) -> None:
                ps.last_user_action = {
                    "action": f"tree:{action}",
                    "status": "ok" if success else "fail",
                    "detail": f"{elapsed * 1000:.0f}ms",
                    "ts": time.monotonic(),
                }
                ps.last_action_at = time.monotonic()
                ps.last_action_label = f"tree {action}"

            tree_task = asyncio.create_task(
                tree_decision_loop(
                    agent,
                    tree_decider,
                    interval_s=tree_interval_s,
                    stop=stop,
                    on_decision=_on_tree_decision,
                )
            )

        try:
            while not stop.is_set():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                await handle_event(event, ps, agent, time.monotonic())
        finally:
            stop.set()
            tasks = [
                poll_state_task,
                poll_events_task,
                poll_decisions_task,
                history_task,
                draw_task,
            ]
            if llm_task is not None:
                tasks.append(llm_task)
            if tree_task is not None:
                tasks.append(tree_task)
            for task in tasks:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
            encoder.close()
            display.close()


async def _prime_state(agent: CosmergonAgent, ps: PetState) -> None:
    """Initial state + registration. The SDK auto-registers on the first call."""
    try:
        await agent._resolve_agent_id()  # type: ignore[attr-defined]
        ps.connection_ok = True
    except Exception as err:
        ps.last_error = str(err)[:30]


async def _poll_state(agent: CosmergonAgent, ps: PetState, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            resp = await agent._request(  # type: ignore[attr-defined]
                "GET", f"/api/v1/agents/{agent.agent_id}/state"
            )
            if resp.status_code == 200:
                state = GameState.from_api(resp.json())
                ps.game_state = state
                # Mirror into the SDK's own state slot so consumers that read
                # `agent.state` (third-party hooks) see the latest snapshot
                # without polling again. Pet runs its own loop instead of the
                # SDK's `on_tick` driver, so `_state` would otherwise stay
                # `None`.
                #
                # SUPERSEDED as a *fix* (S306): this line was added on
                # 2026-05-04 because the LLM decider ran on an empty GameState
                # and `_build_action_choices` collapsed to the `wait` line —
                # diagnosed via the v0.1.19 prompt-dump (3/3 rounds showed
                # `world="(no state available …)"` while `ps.game_state` was
                # filled and `/state` returned 200 OK). Patching a *consumer's*
                # missing input from the outside left the real gap open: a loop
                # that cannot work without the state also did not ask for it,
                # and stayed quiet when it was absent. Both loops now obtain it
                # themselves (`agent_state.StateSource`), so this mirror is a
                # convenience — saving them a redundant request — and no longer
                # the thing that makes decisions work. Do not treat it as
                # load-bearing; if it goes, the deciders keep deciding.
                agent._state = state  # intentional cross-module sync
                ps.connection_ok = True
                ps.last_error = ""
                ps.last_state_poll_at = time.monotonic()
        except Exception as err:
            ps.connection_ok = False
            ps.last_error = f"state: {err}"[:30]
        await asyncio.sleep(STATE_POLL_SECONDS)


async def _poll_events(agent: CosmergonAgent, ps: PetState, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            ps.events = await agent.get_events(limit=20)
            ps.last_events_poll_at = time.monotonic()
        except Exception as err:
            ps.last_error = f"events: {err}"[:30]
        await asyncio.sleep(EVENTS_POLL_SECONDS)


async def _poll_decisions(agent: CosmergonAgent, ps: PetState, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            ps.last_decision = await agent.get_last_decision()
            ps.last_decisions_poll_at = time.monotonic()
        except Exception as err:
            ps.last_error = f"decisions: {err}"[:30]
        await asyncio.sleep(DECISION_POLL_SECONDS)


async def _history_loop(agent: CosmergonAgent, ps: PetState, stop: asyncio.Event) -> None:
    """Holt den Energie-Verlauf für alle Fenster des Verlaufs-Schirms.

    Getrennt von den übrigen Abfragen, weil er sich langsam ändert: alle fünf
    Minuten genügt für eine 24-Stunden-Kurve, deren feinste Stützstelle 15
    Minuten breit ist. Häufiger abzufragen würde die Anzeige nicht verbessern,
    aber die Funkstrecke des Pi belasten.
    """
    while not stop.is_set():
        for fenster, _ in HISTORY_WINDOWS:
            try:
                punkte = await agent.get_balance_history(window=fenster)
                if punkte:
                    ps.balance_history[fenster] = [float(p["balance"]) for p in punkte]
                    ps.last_history_poll_at = time.monotonic()
            except Exception as err:  # Anzeige darf nie ausfallen — nur melden
                logger.warning("balance-history %s: %s", fenster, err)
                ps.last_error = f"history: {err}"[:30]
        await asyncio.sleep(HISTORY_POLL_SECONDS)


def aktuelles_fenster(now: float) -> tuple[str, str]:
    """Welches Zeitfenster der Verlaufs-Schirm gerade zeigt.

    Reine Zeitfunktion ohne Zustand: bei jedem Bild neu berechnet, damit der
    Wechsel nicht von der Bildrate abhängt.
    """
    n = int(now / HISTORY_SWITCH_SECONDS) % len(HISTORY_WINDOWS)
    return HISTORY_WINDOWS[n]


def _is_idle(ps: PetState, now: float) -> bool:
    """Screensaver eligibility: idle on screen 1, no menu, beyond threshold."""
    if ps.menu_open or ps.current_screen != 0:
        return False
    last_input = max(ps.last_rotation_at, ps.last_action_at)
    if last_input == 0.0:
        # Service just started — count from process start (=monotonic 0). Since
        # `now` is monotonic time, the loop will trip into screensaver after
        # SCREENSAVER_AFTER_SECONDS of pure runtime if no input ever arrives.
        return now > SCREENSAVER_AFTER_SECONDS
    return (now - last_input) > SCREENSAVER_AFTER_SECONDS


async def _draw_loop(display: Any, ps: PetState, stop: asyncio.Event) -> None:
    interval = 1.0 / DISPLAY_REFRESH_HZ
    while not stop.is_set():
        try:
            now = time.monotonic()
            if not _is_idle(ps, now):
                interval = 1.0 / DISPLAY_REFRESH_HZ
                if ps.current_screen == 0 and not ps.menu_open and hasattr(display, "draw_verlauf"):
                    # Schirm 1 ist der Verlauf (Gründer 22.08.2026). Im Menü
                    # nicht — dort muss die Auswahl lesbar bleiben.
                    fenster, label = aktuelles_fenster(now)
                    st = ps.game_state
                    display.draw_verlauf(
                        st.agent_name if st and st.agent_name else "agent",
                        ps.balance_history.get(fenster, []),
                        label,
                        float(st.energy) if st else 0.0,
                    )
                else:
                    display.draw(render_screen(ps, now))
            elif hasattr(display, "draw_eyes"):
                # Gezeichnete Augen (OLED): höhere Bildrate, weil hier animiert
                # wird. Der Zustand geht roh hinein — die Übersetzung in eine
                # Augenform gehört ins Display, nicht in den Ablauf.
                interval = 1.0 / SCREENSAVER_REFRESH_HZ
                display.draw_eyes(mood_from_state(ps, now), now, blink=poll_just_fired(ps, now))
            elif hasattr(display, "draw_big_face"):
                # Terminal-Simulation: dort gibt es keine Pixel, das ASCII-
                # Gesicht bleibt die Darstellung.
                interval = 1.0 / DISPLAY_REFRESH_HZ
                face = apply_blink(FACES[mood_from_state(ps, now)], ps, now)
                display.draw_big_face(face, cell_count=total_active_cells(ps))
            else:
                display.draw(render_screen(ps, now))
        except Exception:
            logger.exception("draw failed")
        await asyncio.sleep(interval)


# ----------------------------------------------------------------------------
# Entry Point
# ----------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Cosmergon Pet — stage 1")
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run without RPi hardware: console display, arrow keys + Enter/Space.",
    )
    parser.add_argument("--log-level", default="WARNING", help="DEBUG/INFO/WARNING/ERROR")
    parser.add_argument(
        "--with-llm",
        default=None,
        metavar="PROVIDER",
        help=(
            "Enable autonomous LLM-driven decisions. Provider name from "
            "cosmergon_pet.llm.available_providers() (today: 'ollama'). "
            "Configure via env vars, e.g. PET_LLM_OLLAMA_URL=http://mac-mini.local:11434 "
            "and PET_LLM_OLLAMA_MODEL=llama3.2:3b."
        ),
    )
    parser.add_argument(
        "--llm-interval-s",
        type=float,
        default=60.0,
        help="Seconds between LLM decisions (default: 60, matches Cosmergon tick).",
    )
    parser.add_argument(
        "--with-tree-decider",
        action="store_true",
        help=(
            "Enable autonomous decisions via the rule-based TreeDecider "
            "(no LLM, no Ollama, no model file — pure-Python persona-tree). "
            "Mutually exclusive with --with-llm. Mirrors lab-cluster's tree-lane."
        ),
    )
    parser.add_argument(
        "--tree-interval-s",
        type=float,
        default=60.0,
        help="Seconds between tree decisions (default: 60, matches Cosmergon tick).",
    )
    args = parser.parse_args()

    if args.with_llm is not None and args.with_tree_decider:
        parser.error("--with-llm and --with-tree-decider are mutually exclusive.")

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.WARNING),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    api_key = os.environ.get("COSMERGON_API_KEY")
    base_url = os.environ.get("COSMERGON_BASE_URL", "https://cosmergon.com")
    agent = CosmergonAgent(api_key=api_key, base_url=base_url)

    llm_provider = None
    tree_decider = None
    if args.with_llm is not None:
        from .llm import build_provider

        llm_provider = build_provider(args.with_llm)
        logging.getLogger(__name__).info(
            "LLM enabled: %s (interval %.1fs)",
            llm_provider.model_string,
            args.llm_interval_s,
        )
    elif args.with_tree_decider:
        from .decider_tree import TreeDecider

        tree_decider = TreeDecider()
        logging.getLogger(__name__).info(
            "TreeDecider enabled (rule-based, interval %.1fs)",
            args.tree_interval_s,
        )

    try:
        asyncio.run(
            run_pet(
                agent,
                simulate=args.simulate,
                llm_provider=llm_provider,
                llm_interval_s=args.llm_interval_s,
                tree_decider=tree_decider,
                tree_interval_s=args.tree_interval_s,
            )
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
