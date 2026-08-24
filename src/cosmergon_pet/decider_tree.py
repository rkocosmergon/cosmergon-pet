"""TreeDecider v2.3.1 — Subsistenz + Persona-Charakter (GOBT-Pattern).

VENDORED from ``cosmergon-decider-tree`` (private cosmergon repo,
``research/decider-cluster/decider-tree/``).

v2.3.1 changes (S308, am Live-Fall Socket-hand):
  - Kaufabsicht statt Blindkauf (Server-P3b-Analog): market_buy entsteht
    NUR noch aus einer Absicht — preset-Nachschub (Feld vorhanden,
    ``market_buy.preset_stock`` < 3, Server >= v1.65.4) oder mega_bomb
    fuer die Feldlos-Kette (Ziele sichtbar, Arsenal < 3). EIN Kern
    (``_gewolltes_buyable``) fuer is_valid, Resolver und Delta — ein Gate
    an einem von zwei Eingaengen ist keines. Ohne Server-Faktum (aelter
    als v1.65.4) bleibt der Legacy-Typ-Filter durchlaessig wie bisher.
    Anlass: Socket-hand (diplomat) kaufte 203 Haus-Presets in 24 h — der
    Baum begruendete jeden Kauf mit dem billigsten erlaubten Listing.

v2.2.x changes (S307, am Live-Fall Socket-hand):
  - v2.2.0: Eroberungs-Kette fuer Feldlose in ``_resolve_start_mission`` —
    der Server (>= v1.64.143) nennt mega_bombs/richest_loot_field/Ziel-IDs
    im State; gather braucht KEIN eigenes Feld, siege ab 3 Bomben, die
    Folge-capture spawnt der Server.
  - v2.2.1: die Kette ist auch ERREICHBAR. Socket-hand sass im
    Subsistenz-Gefaengnis: Schwelle 20k > 10k Guthaben -> Subsistenz-Pool,
    und dort war market_list der einzige gueltige Zug (place_cells braucht
    ein Feld, create_field einen freien Slot) — das wochenlange
    Markt-Karussell war eine POOL-Eigenschaft, kein LLM-Fehler.
    start_mission gehoert in den Subsistenz-Pool (kostet 0 Energie, ist
    neben create_field die einzige nachhaltige Income-Quelle), Score 0.9
    fuer Feldlose vor dem delta-Guard (_predict_delta modelliert
    Missionen nicht).

v2.1.3 changes (S298, an der Live-Kadenz gemessen):
  - Vertrags-``duration`` 100 -> 1000 Ticks. 100 (~2,5 h) machte Pakte zu
    Drehtuer-Vertraegen: der Server schliesst Verpaktete aus den
    contract_targets aus, nach Expiry sind sie wieder Kandidat — Comet-hand
    schloss 34 Pakte in 75 min und haette das endlos rolliert. 1000 ist die
    Beziehungs-Zeitskala der Hauptwelt (CAPTURE_COOLDOWN_TICKS), keine
    gesetzte Zahl; daempft die Kadenz ~Faktor 7 und macht den Pakt echt.

v2.1.2 changes (S298, gleicher Tag — der Backoff legte den naechsten frei):
  - propose_from_template: template_id/mode/slots reisen im ``params``-
    Sub-Dict (ActionRequest kennt sie nicht flach -> 422 bei jedem Versuch)
    und nur Free-Tier-konforme Templates T07/T08 (T09/T06 rendern zu
    alliance/tribute = 402-Klasse des direkten Wegs).

v2.1.1 changes (S298, vom v2.1.0-Backoff freigelegt):
  - propose_contract: Vertragstyp UND Terms je Persona aus der
    Backend-Wahrheit. Vorher erfand der Baum "research_agreement"
    (existiert im Backend nicht) und sandte trade_agreement ohne den
    Pflicht-Term ``fee_discount_pct`` — beide Formen liefen bei jedem
    Versuch in HTTP 400 (Comet-hand: 156x in 22 h, nur vom Backoff
    gedrosselt).

v2.1.0 changes (S297, am Live-Fall Comet-hand):
  - market_list liest die SERVER-Wahrheit (``available_actions.market_list``:
    ``sellable_energy`` + ``sellable_items``, Backend >= v1.64.30) statt einer
    eigenen 1500er-Schwelle, die der S278-Deckungsregel widersprach.
  - market_list kann gedeckte INVENTAR-Items listen (Preis = 95 % des
    billigsten aktiven Listings desselben Typs — nie eine eigene Konstante).
  - start_mission: ``reward_energy`` immer 0 (S278-Selbstbelohnungs-Tor lehnt
    jede Selbst-Mission mit reward > 0 ab) + Params nur mit echten UUIDs
    (None-IDs waren garantierte 422).
  - ``decide(state, blocked=...)``: der Loop kann Aktionen nach wiederholten
    identischen Fehlschlaegen temporaer sperren (Backoff im Loop, Decider
    bleibt zustandslos).

This is a **Major architecture change** vs Pet 0.1.33 (which had Tree
v1.1.4 first-match-cascading). v2.0.2 is GOBT (Goal-Oriented Behavior
Tree): Subsistenz-Layer (universal) + Persona-Kern-Charakter (6 individual
cycles) + generic score-function with goal-metric. Stateless,
deterministic, sub-ms, explainable.

v2.0.2 changes (vs. v1.1.4 in Pet 0.1.33):
  - Layer 1 Subsistenz: when energy < persona-specific threshold,
    Pet earns energy (place_cells / market_list / create_field).
  - Layer 2 Persona-Charakter: 6 individual life cycles
    (scientist/trader/warrior/expansionist/diplomat/farmer), each
    with own action pool, persona bias, goal metric.
  - Score function generic with goal-metric argument
    (energy_at_least, avg_cells_at_least, evolved_fields, etc.).
  - Direction-based scoring (v2.0.2 fix): actions in right direction
    get score ≥ 0.7 even at low magnitude — fixes
    Pulsar-eye-pattern where +3 cells / 403 fields was scored 0.0003.
  - Persona-Bias additive [-0.3, +0.3], goal logic dominant.
  - Compass = additional bias modifier [-0.2, +0.2].
  - Catastrophe-Recovery implicit via Subsistenz layer switch.
  - PERSONA_BUYABLE_TYPES filter (v1.1.4 heritage, anti-hoarding).
  - 15% safety margin on _can_afford_field (v1.1.3 heritage,
    decide/execute race protection).

Both Pet's vendored files (decider_tree.py + persona_profiles.py) must
be re-vendored together — they form one logical unit. Bump Pet MINOR or
MAJOR version when re-vendoring (this is Pet 0.2.0 — major bump because
v2.0.0 architecture replaces v1.x first-match-tree).

Source: docs/konzepte/konzept-decider-tree-v2.md (private cosmergon
repo, S171 5-voice panel + founder review 2026-05-08).
"""

from __future__ import annotations

import logging
from typing import Any

from cosmergon_agent.state import GameState

from cosmergon_pet.persona_profiles import (
    COMPASS_BIAS,
    EVOLUTION_COST_BY_TIER,
    PERSONA_ACTION_BIAS,
    PERSONA_ACTION_POOLS,
    PERSONA_BUYABLE_TYPES,
    SUBSISTENCE_BIAS,
    SUBSISTENCE_POOL,
    needs_subsistence,
    persona_current_goal,
    subsistence_threshold,
)

logger = logging.getLogger(__name__)

VALID_ACTIONS: frozenset[str] = frozenset(
    {
        "place_cells",
        "evolve",
        "create_field",
        "create_cube",
        "transfer_energy",
        "market_list",
        "market_buy",
        "propose_contract",
        # S204 — Pet-Tree-Decider reagiert auf eingehende Verträge.
        "accept_contract",
        "reject_contract",
        # S206 — Marauder-Actions + Mission-System Phase 2.
        "start_mission",
        "cancel_mission",
        "collect_spore",
        "shoot_spore",
        "pickup_drop",
        "transfer_inventory",
        "place_deployable",
        "claim_field",
        "heal_holes",
        "terminal_query",
        "propose_from_template",
        "wait",
    }
)


# S204 — Persona-Bias für eingehende Verträge.
# Tree-Decider akzeptiert/lehnt mit dieser Map ab. Werte 'accept' | 'reject'.
PERSONA_CONTRACT_BIAS: dict[str, dict[str, str]] = {
    "scientist": {
        "trade_agreement": "accept",
        "alliance": "accept",
        "non_aggression": "accept",
        "tribute": "reject",
    },
    "warrior": {
        "non_aggression": "accept",
        "alliance": "accept",
        "tribute": "accept",
        "trade_agreement": "reject",
    },
    "trader": {
        "trade_agreement": "accept",
        "tribute": "accept",
        "non_aggression": "accept",
        "alliance": "reject",
    },
    "diplomat": {
        "alliance": "accept",
        "trade_agreement": "accept",
        "non_aggression": "accept",
        "tribute": "accept",
    },
    "farmer": {
        "trade_agreement": "accept",
        "non_aggression": "accept",
        "tribute": "reject",
        "alliance": "reject",
    },
    "expansionist": {
        "tribute": "accept",
        "non_aggression": "reject",
        "alliance": "reject",
        "trade_agreement": "reject",
    },
}

CRITICAL_ENERGY = 100.0  # Sink-Schutz
FIELD_COST_SAFETY_MARGIN = 1.15  # v1.1.3-Erbe gegen Decide/Execute-Race


# --- State-Accessors (defensive against missing fields) ----------------------


def _energy(state: GameState) -> float:
    return float(getattr(state, "energy", 0) or 0)


def _fields(state: GameState) -> list[Any]:
    return list(getattr(state, "fields", []) or [])


def _universe_cubes(state: GameState) -> list[Any]:
    """Cubes mit freiem Slot — die Frage „wo koennte ich ein Feld anlegen".

    NUR fuer `create_field` verwenden. Fuer Navigation und Aufklaerung ist
    `_reachable_cubes` richtig: ein Terminalbesuch braucht keinen freien Slot,
    und in einer besiedelten Welt ist DIESE Liste zwangslaeufig leer.
    """
    return list(getattr(state, "universe_cubes", []) or [])


def _reachable_cubes(state: GameState) -> list[Any]:
    """Cubes, die der Koerper erreichen kann — ohne Slot-Filter (S306).

    Faellt auf `universe_cubes` zurueck, wenn der Server das Feld noch nicht
    kennt (Backend < S306). Ohne diesen Rueckfall verloeren aeltere Server
    still die Terminal-Wahl.
    """
    erreichbar = list(getattr(state, "reachable_cubes", []) or [])
    return erreichbar or _universe_cubes(state)


def _market_buyable(state: GameState) -> list[Any]:
    wb = getattr(state, "world_briefing", None)
    market = getattr(wb, "market", None) if wb is not None else None
    return list(getattr(market, "buyable", ()) or [])


def _contract_targets(state: GameState) -> list[Any]:
    wb = getattr(state, "world_briefing", None)
    return list(getattr(wb, "contract_targets", ()) or []) if wb is not None else []


def _can_afford_field(state: GameState) -> bool:
    """Backend-truth via state.available_actions["create_field"], plus 15%-Margin."""
    actions = getattr(state, "available_actions", None) or {}
    create = actions.get("create_field") if isinstance(actions, dict) else None
    if not isinstance(create, dict):
        return False
    next_cost = create.get("next_cost")
    if next_cost is not None:
        try:
            return _energy(state) >= float(next_cost) * FIELD_COST_SAFETY_MARGIN
        except (TypeError, ValueError):
            pass
    if "can_afford" in create:
        return bool(create["can_afford"])
    return False


def _next_field_cost(state: GameState) -> float:
    actions = getattr(state, "available_actions", None) or {}
    create = actions.get("create_field") if isinstance(actions, dict) else None
    if isinstance(create, dict) and create.get("next_cost") is not None:
        try:
            return float(create["next_cost"])
        except (TypeError, ValueError):
            return 500.0 * len(_fields(state))
    return 500.0 * len(_fields(state))


# --- Persona-spezifische preset-Wahl ----------------------------------------

PERSONA_PREFERRED_PRESETS: dict[str, str] = {
    "scientist": "blinker",  # T1-oscillator, Vorbereitung für T2-evolve
    "expansionist": "blinker",  # gleicher Pfad
    "farmer": "blinker",
    "warrior": "block",  # still_life als Territorial-Markierung
    "trader": "block",  # billig
    "diplomat": "block",
}

_PRESET_COST: dict[str, int] = {
    "block": 5,
    "blinker": 10,
    "toad": 50,
    "glider": 200,
    "r_pentomino": 200,
}


def _persona_preferred_preset(state: GameState) -> str:
    persona = (getattr(state, "persona_type", None) or "scientist").lower()
    preferred = PERSONA_PREFERRED_PRESETS.get(persona, "block")
    if _energy(state) >= _PRESET_COST.get(preferred, 5):
        return preferred
    return "block"


# --- Validity-Filter ---------------------------------------------------------


def _evolve_moeglich(state: GameState) -> bool:
    """Existiert ein Field, das evolve-eligible UND bezahlbar ist?"""
    REIFE_THRESHOLDS = {2: 100, 3: 500, 4: 2000, 5: 10000}
    TYPE_FOR_TIER = {2: "oscillator", 3: "spaceship", 4: "gun", 5: "breeder"}
    energy = _energy(state)
    for f in _fields(state):
        tier = getattr(f, "entity_tier", 0) or 0
        if not isinstance(tier, int) or tier <= 0 or tier >= 5:
            continue
        next_tier = tier + 1
        reife = getattr(f, "reife_score", 0) or 0
        if reife < REIFE_THRESHOLDS.get(next_tier, 999_999):
            continue
        required_type = TYPE_FOR_TIER.get(next_tier)
        if required_type and getattr(f, "entity_type", None) != required_type:
            continue
        cost = EVOLUTION_COST_BY_TIER.get(tier, 0)
        if energy < cost:
            continue
        return True
    return False


def _market_buy_moeglich(state: GameState) -> bool:
    """Gibt es einen Kauf MIT Absicht (v2.3.1 — ohne Absicht keinen)?"""
    persona = (getattr(state, "persona_type", None) or "scientist").lower()
    return _gewolltes_buyable(state, persona) is not None


def _start_mission_moeglich(state: GameState) -> bool:
    """Marauder in recovery, keine aktive Mission, Params FUELLBAR (v2.1.0:
    echte UUIDs — ein feldloser Agent in voller Welt hat keinen Kandidaten,
    und ein {}-Versuch wäre ein garantierter 422)."""
    # v2.2.3 (S307): getattr(state, "marauder_state"/"my_mission") war TOTER
    # Code — das SDK-GameState traegt beide Felder nicht, die Guards liefen
    # immer ins Default. Die SERVER-Wahrheit steht seit v1.64.143 in
    # available_actions.start_mission.marauder_state; None heisst "Server
    # nennt sie nicht" (aelter) und bleibt durchlaessig wie bisher.
    fakten = (getattr(state, "available_actions", None) or {}).get("start_mission") or {}
    server_zustand = fakten.get("marauder_state")
    if server_zustand is not None and server_zustand != "recovery":
        return False
    if getattr(state, "my_mission", None) is not None:
        return False
    persona_v = (getattr(state, "persona_type", None) or "scientist").lower()
    return bool(resolve_action_params(state, "start_mission", persona_v))


def is_valid(state: GameState, action: str) -> bool:
    """Vor-Backend-Validity-Check. Verhindert dass Tree eine Action wählt,
    die das Backend mit 400 ablehnen würde."""
    if action == "wait":
        return True

    if _energy(state) < CRITICAL_ENERGY:
        return action == "wait"  # nur wait erlaubt im Critical-Modus

    if action == "create_field":
        return _can_afford_field(state) and len(_universe_cubes(state)) > 0

    if action == "place_cells":
        if len(_fields(state)) == 0:
            return False
        # Cheapest preset (block) muss bezahlbar sein
        return _energy(state) >= _PRESET_COST["block"]

    if action == "evolve":
        return _evolve_moeglich(state)

    if action == "market_buy":
        return _market_buy_moeglich(state)

    if action == "market_list":
        # v2.1.0 (S297): Server-Wahrheit statt eigener Schwelle — siehe
        # _market_list_plan. Die alte Regel (energy >= 1500) widersprach der
        # S278-Deckungsregel des Backends: Comet-hand (9.953 Guthaben, unter
        # dem Zerfalls-Freibetrag) listete minutenlang ins 400.
        return _market_list_plan(state) is not None

    if action == "propose_contract":
        return len(_contract_targets(state)) > 0 and _energy(state) >= 5_000

    if action == "transfer_energy":
        return False  # nicht in v2.0.0-Action-Pool

    # S206 Marauder-Mission-System Phase 2.
    if action == "start_mission":
        return _start_mission_moeglich(state)
    if action == "cancel_mission":
        return getattr(state, "my_mission", None) is not None

    # S206 Item-Pickups: Pet ohne Marauder-Position-State kann das nicht
    # autonom triggern (braucht Spore-/Drop-ID + Distance-Check). Tree-Decider
    # lässt das aus, Pet-User triggert manuell oder via LLM-Decider.
    if action in ("collect_spore", "shoot_spore", "pickup_drop", "transfer_inventory"):
        return False  # nicht Tree-autonom

    if action == "place_deployable":
        # Braucht Inventory + Marauder-Position — Tree-Decider lässt das aus.
        return False

    if action == "claim_field":
        # Capture braucht Marauder am vulnerable Target — Mission-Pfad-Domäne.
        return False
    if action == "heal_holes":
        # Eigenes Field mit hole_count > 0 + Energy. Mission-Pfad bevorzugt.
        return False
    if action == "terminal_query":
        # Braucht Marauder am Cube-Center-Terminal — Mission-Pfad.
        return False
    if action == "propose_from_template":
        return len(_contract_targets(state)) > 0 and _energy(state) >= 5_000

    return False


# --- Action-Parameter-Resolver -----------------------------------------------


_PERSONA_ENERGY_LIST_PRICE: dict[str, int] = {
    "trader": 500,
    "scientist": 450,
    "warrior": 400,
    "expansionist": 400,
    "diplomat": 450,
    "farmer": 450,
}


def _markt_referenzpreise(state: GameState, ml: dict[str, Any]) -> dict[str, float]:
    """Referenzpreise je Item-Typ — bevorzugt vom Server (`reference_prices`,
    Backend >= v1.64.31: billigstes aktives Fremd-Listing je Typ; das
    Markt-Briefing traegt nur die 20 billigsten Listings insgesamt und laesst
    hochpreisige Typen wie mega_bomb unsichtbar). Fallback: das Briefing."""
    referenz: dict[str, float] = {}
    server_ref = ml.get("reference_prices")
    if isinstance(server_ref, dict):
        for it, preis in server_ref.items():
            try:
                referenz[str(it)] = float(preis)
            except (TypeError, ValueError):
                continue
    if not referenz:
        for b in _market_buyable(state):
            it = getattr(b, "item_type", None)
            preis = getattr(b, "price_energy", None)
            try:
                preis_f = float(preis)
            except (TypeError, ValueError):
                continue
            if it and (it not in referenz or preis_f < referenz[it]):
                referenz[it] = preis_f
    return referenz


def _market_list_plan(state: GameState) -> dict[str, Any] | None:
    """Was KANN dieser Agent listen? Eine Quelle für is_valid + resolve (v2.1.0).

    Liest die Server-Wahrheit aus ``available_actions["market_list"]``
    (Backend >= v1.64.30: ``available`` + ``sellable_energy`` +
    ``sellable_items``). Energie nur bei Überschuss über dem
    Zerfalls-Freibetrag (S278-Deckungsregel); gedeckte Inventar-Items gehen
    immer — Preis kommt vom billigsten aktiven Listing desselben Typs im
    Markt-Briefing (5 % darunter), NIE aus einer eigenen Konstante (die
    würde gegen die Welt driften). Ohne Referenzpreis wird nicht gelistet.

    Ältere Backends ohne die sellable_*-Schlüssel: alte 1500er-Schwelle.
    """
    persona = (getattr(state, "persona_type", None) or "scientist").lower()
    energy_price = _PERSONA_ENERGY_LIST_PRICE.get(persona, 450)

    actions = getattr(state, "available_actions", None) or {}
    ml = actions.get("market_list") if isinstance(actions, dict) else None
    if not isinstance(ml, dict) or "sellable_energy" not in ml:
        # Alter Server — keine Wahrheit verfügbar, altes Verhalten.
        if _energy(state) >= 1_500:
            return {"price_energy": energy_price}
        return None

    if not ml.get("available"):
        return None

    try:
        if float(ml.get("sellable_energy") or 0) > 0:
            return {"price_energy": energy_price}
    except (TypeError, ValueError):
        pass

    items = ml.get("sellable_items") or {}
    if not isinstance(items, dict) or not items:
        return None
    referenz = _markt_referenzpreise(state, ml)
    # Wertvollstes referenzierbares Item zuerst — totes Kapital zu Geld.
    kandidaten = [(referenz[t], t) for t, n in items.items() if t in referenz and (n or 0) > 0]
    if not kandidaten:
        return None
    kandidaten.sort(reverse=True)
    ref_preis, item_type = kandidaten[0]
    return {
        "item_type": item_type,
        "item_data": {"count": 1},
        "price_energy": max(round(ref_preis * 0.95), 10),
    }


def _fewest_cells_field(state: GameState) -> Any | None:
    fs = _fields(state)
    if not fs:
        return None
    return min(fs, key=lambda f: getattr(f, "active_cell_count", 0) or 0)


def _empty_field(state: GameState) -> Any | None:
    for f in _fields(state):
        if (getattr(f, "active_cell_count", 0) or 0) == 0:
            return f
    return None


def _cheapest_evolvable_field(state: GameState) -> Any | None:
    REIFE_THRESHOLDS = {2: 100, 3: 500, 4: 2000, 5: 10000}
    TYPE_FOR_TIER = {2: "oscillator", 3: "spaceship", 4: "gun", 5: "breeder"}
    energy = _energy(state)
    eligible = []
    for f in _fields(state):
        tier = getattr(f, "entity_tier", 0) or 0
        if not isinstance(tier, int) or tier <= 0 or tier >= 5:
            continue
        next_tier = tier + 1
        reife = getattr(f, "reife_score", 0) or 0
        if reife < REIFE_THRESHOLDS.get(next_tier, 999_999):
            continue
        required_type = TYPE_FOR_TIER.get(next_tier)
        if required_type and getattr(f, "entity_type", None) != required_type:
            continue
        cost = EVOLUTION_COST_BY_TIER.get(tier, 0)
        if energy < cost:
            continue
        eligible.append((cost, f))
    if not eligible:
        return None
    eligible.sort(key=lambda p: p[0])
    return eligible[0][1]


def _cheapest_buyable(state: GameState, persona: str) -> Any | None:
    allowed = PERSONA_BUYABLE_TYPES.get(persona, ("cube", "field"))
    energy = _energy(state)
    candidates = []
    for b in _market_buyable(state):
        if allowed is not None:
            if getattr(b, "item_type", None) not in allowed:
                continue
        price = getattr(b, "price_energy", None)
        try:
            price_f = float(price) if price is not None else None
        except (TypeError, ValueError):
            continue
        if price_f is None or price_f > energy:
            continue
        candidates.append((price_f, b))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p[0])
    return candidates[0][1]


def _kauf_absichten(state: GameState) -> tuple[str, ...] | None:
    """v2.3.1 (S308) — Kaufabsicht statt Blindkauf (Server-P3b-Analog).

    ``None`` heisst: der Server nennt ``market_buy.preset_stock`` nicht
    (aelter als v1.65.4) — der Aufrufer faellt auf den Legacy-Typ-Filter
    zurueck (Durchlaessigkeits-Muster wie ``marauder_state``). Anlass:
    Socket-hand (diplomat) kaufte 203 Haus-Presets in 24 h, weil der Baum
    jeden Kauf mit dem billigsten erlaubten Listing begruendete — ein
    Vorrats-Gate war clientseitig strukturell unmoeglich (der State trug
    kein Inventar).
    """
    verfuegbar = getattr(state, "available_actions", None) or {}
    stock = (verfuegbar.get("market_buy") or {}).get("preset_stock")
    if stock is None:
        return None
    wuensche: list[str] = []
    # Saat-Nachschub: eigenes Feld vorhanden und Vorrat < 3 (Server-P3b-Grenze,
    # utility_selector._preset_absicht — dieselbe Zahl, dieselbe Bedeutung).
    if _fields(state) and int(stock) < 3:
        wuensche.append("preset")
    # Bomben fuer die Feldlos-Kette: Ziele sichtbar und Arsenal < 3 (dieselbe
    # Schwelle wie _feldlos_eroberungs_zug: siege ab 3) — der Kauf ist der
    # Beschleuniger des Sammelns, nicht sein Ersatz.
    sm_fakten = verfuegbar.get("start_mission") or {}
    ziele = (verfuegbar.get("claim_field") or {}).get("targets") or []
    if not _fields(state) and ziele and int(sm_fakten.get("mega_bombs") or 0) < 3:
        wuensche.append("mega_bomb")
    return tuple(wuensche)


def _gewolltes_buyable(state: GameState, persona: str) -> Any | None:
    """Der EINE Kauf-Kern fuer alle drei Eingaenge (is_valid, Resolver,
    Delta) — ein Gate an einem von zwei Eingaengen ist keines.

    v2.3.1: die Absicht ERSETZT den statischen PERSONA_BUYABLE_TYPES-Filter,
    dessen Anti-Hoarding-Ziel sie schaerfer erfuellt (kaufe nur, was du JETZT
    brauchst); der Filter wirkt nur noch im Legacy-Zweig fuer aeltere Server.
    """
    absichten = _kauf_absichten(state)
    if absichten is None:
        return _cheapest_buyable(state, persona)
    if not absichten:
        return None
    energy = _energy(state)
    candidates = []
    for b in _market_buyable(state):
        if getattr(b, "item_type", None) not in absichten:
            continue
        try:
            price_f = float(getattr(b, "price_energy", None))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if price_f > energy:
            continue
        candidates.append((price_f, b))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p[0])
    return candidates[0][1]


def resolve_action_params(state: GameState, action: str, persona: str) -> dict[str, Any]:
    """Best-effort Parameter-Auswahl für die gewählte Action."""
    if action == "create_field":
        cubes = _universe_cubes(state)
        return {"cube_id": str(cubes[0].id)} if cubes else {}

    if action == "place_cells":
        # Bevorzuge empty_field, sonst fewest_cells
        target = _empty_field(state) or _fewest_cells_field(state)
        if target is None:
            return {}
        return {"field_id": str(target.id), "preset": _persona_preferred_preset(state)}

    if action == "evolve":
        f = _cheapest_evolvable_field(state)
        return {"field_id": str(f.id)} if f else {}

    if action == "market_buy":
        b = _gewolltes_buyable(state, persona)
        return {"listing_id": str(b.listing_id)} if b else {}

    if action == "market_list":
        # v2.1.0: eine Quelle mit is_valid — Energie bei Überschuss, sonst
        # gedecktes Inventar-Item zum Markt-Referenzpreis.
        return _market_list_plan(state) or {}

    if action == "propose_contract":
        return _resolve_propose_contract(state, persona)

    # S206 Mission-System.
    if action == "start_mission":
        return _resolve_start_mission(state, persona)

    if action == "cancel_mission":
        return {}

    if action == "propose_from_template":
        return _resolve_propose_from_template(state, persona)

    return {}


def _resolve_propose_contract(state: GameState, persona: str) -> dict[str, Any]:
    """Vertragstyp UND Terms je Persona aus der Backend-Wahrheit.

    v2.1.1 (S298): Referenz sind models/contract.py:CONTRACT_TYPES + das
    Free-Tier-Gate agent_game.py:_FREE_CONTRACT_TYPES = {non_aggression,
    trade_agreement}. Vorher erfand der Baum "research_agreement" (existiert
    im Backend nicht -> validate_terms "Unknown contract type" -> HTTP 400,
    bei Comet-hand 156x in 22 h), und trade_agreement lief ohne den
    Pflicht-Term fee_discount_pct (required laut Schema) in dieselbe 400.
    """
    targets = _contract_targets(state)
    if not targets:
        return {}
    target = targets[0]
    contract_plan = {
        "scientist": ("non_aggression", {"duration": 1000}),
        "trader": ("trade_agreement", {"fee_discount_pct": 10, "duration": 1000}),
        "warrior": ("non_aggression", {"duration": 1000}),
        "diplomat": ("non_aggression", {"duration": 1000}),
        "farmer": ("trade_agreement", {"fee_discount_pct": 10, "duration": 1000}),
        "expansionist": ("non_aggression", {"duration": 1000}),
    }
    contract_type, terms = contract_plan.get(persona, ("non_aggression", {"duration": 1000}))
    return {
        "to_player_id": str(target.player_id),
        "contract_type": contract_type,
        # Backend-Validator (contract_manager.validate_terms) erwartet
        # API-Term-Key 'duration' (nicht 'duration_ticks' — das ist nur die
        # ORM-Column, models/contract.py:94). Verifiziert 2026-05-09 nach
        # Socket-hand 0/99 success-Empirie auf RPi 4 (S178).
        "terms": terms,
        "escrow_amount": 0,
    }


def _feldlos_eroberungs_zug(state: GameState) -> dict[str, Any] | None:
    """v2.2.x: der situative Zug des Feldlosen — loot -> mega_bombs -> siege.

    None heisst: der Server nennt keine Landweg-Fakten (aelter als v1.64.143)
    — der Aufrufer faellt auf den S306-Scout-Weg zurueck. Schwelle 3 Bomben:
    eine reisst ~12 Loecher (verwundbar ab >5), zwei Reserven gegen Heilung.
    """
    verfuegbar = getattr(state, "available_actions", None) or {}
    sm_fakten = verfuegbar.get("start_mission") or {}
    cf_fakten = verfuegbar.get("claim_field") or {}
    bomben = int(sm_fakten.get("mega_bombs") or 0)
    ziele = cf_fakten.get("targets") or []
    loot = sm_fakten.get("richest_loot_field") or {}
    if bomben >= 3 and ziele:
        return _mission_payload(
            "siege_field",
            {"target_field_id": str(ziele[0]["field_id"]), "deadline_ticks": 2000},
        )
    if loot.get("field_id"):
        return _mission_payload(
            "gather_spores",
            {"field_id": str(loot["field_id"]), "max_items": 10, "duration_ticks": 200},
        )
    return None


def _mission_payload(mission_type: str, mission_params: dict[str, Any]) -> dict[str, Any]:
    """v2.2.2 — der Draht-Vertrag von start_mission, an EINER Stelle.

    ActionRequest kennt mission_type/reward_energy NICHT als Top-Level-Felder;
    Pydantic verwirft Unbekanntes STILL, der Handler liest alles aus
    ``data.params`` — flach gebaute Payloads liefen deshalb IMMER in 422
    "mission_type required" (auch der S306-scout-Fix hat so nie gefeuert;
    die Tests pruefen seitdem die Draht-Form, nicht die Client-Form).
    Gleiche Fehlerklasse wie v2.1.2 bei propose_from_template.
    """
    return {
        "params": {
            "mission_type": mission_type,
            "params": mission_params,
            "reward_energy": 0,
        }
    }


def _resolve_start_mission(state: GameState, persona: str) -> dict[str, Any]:
    """Persona-Affinity-Default — konzept-mission-system §3 + persona-Reform.

    v2.1.0 (S297): reward_energy IMMER 0 — das Backend lehnt jede selbst
    erstellte Mission mit reward > 0 ab (S278-Selbstbelohnungs-Tor: „you
    would be paying yourself out of nothing"). Die 1000 aus v2.0.x waren ein
    garantierter 400. Und: params muessen FUELLBAR sein — das Schema verlangt
    echte UUIDs, ein None-field_id/cube_id ist ein garantierter 422. Lieber
    gar kein Kandidat als ein toter.
    """
    mission_by_persona = {
        "warrior": "gather_spores",  # Arsenal-Aufbau
        "expansionist": "gather_spores",  # Werkzeuge für Cube-Expansion
        "farmer": "gather_spores",  # Erntung
        "scientist": "scout_terminal",  # Intel-Sammeln
        "trader": "deliver_resource",  # Transport-Geschäft
        "diplomat": "patrol_field",  # Diplomatischer Rundgang
    }
    mission_type = mission_by_persona.get(persona, "gather_spores")

    # v2.2.0 (S307) — Eroberungs-Kette fuer Feldlose, VOR dem S306-Notfallweg:
    # der Server nennt seit v1.64.143 Bomben-Bestand, reichstes Loot-Feld und
    # Ziel-IDs direkt im State (`available_actions.start_mission/.claim_field`).
    # Damit ist der Weg zurueck zu Besitz vollstaendig clientseitig planbar:
    # Loot sammeln (gather braucht KEIN eigenes Feld — nur Existenz des Ziels)
    # -> mega_bombs -> siege_field; die Folge-capture spawnt der SERVER selbst
    # (S240/S242), der Client muss die Kette nicht weiterfuehren.
    # Schwelle 3 Bomben: eine reisst ~12 Loecher (verwundbar ab >5), zwei
    # Reserven gegen Heilung — Socket-still gelang die Kette mit 13, das
    # Minimum soll nicht Perfektion verlangen.
    if not _fields(state):
        zug = _feldlos_eroberungs_zug(state)
        if zug is not None:
            return zug

    # S306 — Notfallweg vor Persona: wer KEIN Feld hat, klaert auf, egal welche
    # Persona er traegt. Alle anderen Missionsarten setzen eigenen Besitz
    # voraus (`gather_spores`/`patrol_field` brauchen ein Feld, das es nicht
    # gibt) und liefern `{}` — der Agent bliebe ohne jede Mission.
    # Aufklaerung ist dann kein Stil, sondern der einzige Weg zurueck: das
    # Terminal nennt verwundbare Ziele (`field_lookup`), und daraus wird eine
    # Eroberung. Besitz ist Existenzgrundlage, keine Geschmacksfrage.
    # (Greift seit v2.2.0 nur noch, wenn der Server die Landweg-Fakten NICHT
    # liefert — aeltere Server als v1.64.143.)
    if not _fields(state) and _reachable_cubes(state):
        mission_type = "scout_terminal"

    if mission_type == "scout_terminal":
        # S306: erreichbare Cubes, nicht Bauplaetze. Vorher stand hier
        # `_universe_cubes` — in einer vollen Welt immer leer, wodurch die
        # Terminal-Mission auf `gather_spores` zurueckfiel und ein feldloser
        # Agent dort endgueltig strandete.
        cubes = _reachable_cubes(state)
        if not cubes:
            mission_type = "gather_spores"  # Fallback auf den Feld-Weg
        else:
            return _mission_payload(
                "scout_terminal",
                {"cube_id": str(cubes[0].id), "query_type": "wealth_estimate"},
            )
    fields = _fields(state)
    if not fields:
        return {}
    return _mission_payload(
        "gather_spores",
        {"field_id": str(fields[0].id), "max_items": 10, "duration_ticks": 200},
    )


def _resolve_propose_from_template(state: GameState, persona: str) -> dict[str, Any]:
    """Persona-spezifische Template-Wahl (S204 konzept-vertrags-vorlagen).

    v2.1.2 (S298): zwei Korrekturen am Live-Fall Comet-hand.
    (1) template_id/mode/slots MUESSEN im ``params``-Sub-Dict reisen:
    das SDK legt act()-kwargs flach in den Body, ActionRequest kennt diese
    Felder aber nicht (Pydantic verwirft sie) — der Handler las None und
    antwortete 422 "params.template_id required", bei jedem Versuch.
    (2) Nur Free-Tier-konforme Templates (T07/T08): T09_ALLIANCE/T06_TRIBUTE
    rendern zu alliance/tribute, die das Free-Tier-Gate beim direkten
    propose_contract mit 402 ablehnt — der Template-Weg soll dieselbe Regel
    leben, nicht sie umgehen.
    """
    targets = _contract_targets(state)
    if not targets:
        return {}
    t08 = ("T08_NON_AGGRESSION", {})
    t07 = ("T07_TRADE_AGREEMENT", {"fee_discount_pct": 10})
    template_by_persona = {
        "warrior": t08,
        "diplomat": t08,
        "trader": t07,
        "farmer": t07,
        "scientist": t08,
        "expansionist": t08,
    }
    template_id, extra_slots = template_by_persona.get(persona, t08)
    return {
        "params": {
            "template_id": template_id,
            "mode": "targeted",
            "slots": {
                "partner_id": str(targets[0].player_id),
                "duration": 1000,
                **extra_slots,
            },
        },
        "escrow_amount": 0,
    }


# --- Predict-Delta-Funktionen (was ändert die Action am State?) --------------


def _delta_create_field(state: GameState, n_fields: int) -> dict[str, float]:
    """Delta eines Feld-Kaufs: Kosten, +1 Feld, Verwässerung der avg_cells."""
    next_cost = _next_field_cost(state)
    return {
        "energy": -next_cost,
        "field_count": +1,
        "avg_cells": -(
            (
                sum(getattr(f, "active_cell_count", 0) or 0 for f in _fields(state))
                / max(n_fields, 1)
            )
            - (
                sum(getattr(f, "active_cell_count", 0) or 0 for f in _fields(state))
                / max(n_fields + 1, 1)
            )
        ),
    }


def _delta_place_cells(params: dict[str, Any], n_fields: int) -> dict[str, float]:
    """Delta einer Saat: Preset-Kosten + geschätzte Zell-Zunahme."""
    preset = params.get("preset", "block")
    cost = _PRESET_COST.get(preset, 5)
    # blinker fügt ~3 cells, glider ~5, etc. Schätzung:
    cells_added = {"block": 4, "blinker": 3, "toad": 6, "glider": 5, "r_pentomino": 5}.get(
        preset, 4
    )
    avg_cells_delta = cells_added / max(n_fields, 1) if n_fields else 0
    return {
        "energy": -cost,
        "avg_cells": +avg_cells_delta,
        "patterns_established": +1 if preset != "block" else 0,
    }


def _delta_market_buy(state: GameState) -> dict[str, float]:
    """Delta des Kaufs mit Absicht (v2.3.1 — derselbe Kern wie is_valid/Resolver)."""
    b = _gewolltes_buyable(state, (getattr(state, "persona_type", None) or "scientist").lower())
    if b is None:
        return {}
    price = getattr(b, "price_energy", 0) or 0
    item_type = getattr(b, "item_type", None)
    return {
        "energy": -float(price),
        "inventory_growth": +1,
        "is_cube_or_field": 1.0 if item_type in ("cube", "field") else 0.0,
    }


def _delta_start_mission(params: dict[str, Any]) -> dict[str, float]:
    """Mission blockt den Marauder für duration_ticks, kostet upfront
    reward_energy als Reserve. Goal-Effekt je mission_type."""
    mission_type = params.get("mission_type", "")
    reward = float(params.get("reward_energy", 0) or 0)
    delta: dict[str, float] = {"energy": -reward, "active_missions": +1}
    if mission_type == "gather_spores":
        delta["inventory_growth"] = float(params.get("params", {}).get("max_items") or 10)
    elif mission_type == "capture_field":
        delta["field_count"] = +1
    elif mission_type == "heal_holes_field":
        delta["field_health"] = +1
    return delta


def _predict_delta(state: GameState, action: str, params: dict[str, Any]) -> dict[str, float]:
    """Schätzt State-Delta für die Action. Wird vom Score genutzt um
    Goal-Distance-Reduktion zu messen."""
    n_fields = len(_fields(state))

    if action == "wait":
        return {}

    if action == "create_field":
        return _delta_create_field(state, n_fields)

    if action == "place_cells":
        return _delta_place_cells(params, n_fields)

    if action == "evolve":
        # Tier-Aufstieg eines Fields
        f = _cheapest_evolvable_field(state)
        if f is None:
            return {}
        tier = getattr(f, "entity_tier", 1) or 1
        cost = EVOLUTION_COST_BY_TIER.get(tier, 1_000)
        return {"energy": -cost, "evolved_fields": +1}

    if action == "market_buy":
        return _delta_market_buy(state)

    if action == "market_list":
        # Annahme: list-fee marginal, Verkauf ist ungewiss aber positiv
        list_price = params.get("price_energy", 450)
        return {"energy_listed": +float(list_price), "energy": -10.0}  # listing-fee

    if action == "propose_contract":
        return {"energy": -float(params.get("escrow_amount", 0) or 0), "active_contracts": +1}

    # S206 Marauder-Mission-System Phase 2.
    if action == "start_mission":
        return _delta_start_mission(params)

    if action == "cancel_mission":
        return {"active_missions": -1}

    # S206 Item-Pickups + Inventar-Bewegungen.
    if action in ("collect_spore", "pickup_drop", "shoot_spore"):
        return {"inventory_growth": +1}
    if action == "transfer_inventory":
        return {"inventory_growth": -float(params.get("count", 1) or 1)}
    if action == "place_deployable":
        return {"inventory_growth": -1}

    # S206 Capture/Heal/Terminal-Actions.
    if action == "claim_field":
        return {"field_count": +1}
    if action == "heal_holes":
        return {"field_health": +1, "energy": -100.0}
    if action == "terminal_query":
        return {"intel_growth": +1, "energy": -50.0}
    if action == "propose_from_template":
        # template-spezifischer escrow im params['escrow_amount']
        return {
            "energy": -float(params.get("escrow_amount", 0) or 0),
            "active_contracts": +1,
        }

    return {}


# --- Score-Funktion (generisch, mit Goal-Metric) -----------------------------


def _feldloser_missions_zug(
    state: GameState, action: str, params: dict[str, Any], goal_metric: dict[str, Any]
) -> bool:
    """v2.2.1 (S307): Feldlos ist die Eroberungs-Kette neben create_field die
    einzige NACHHALTIGE Income-Quelle — market_list ist ein Einmal-Boost.
    Eigenes Praedikat, weil _predict_delta Missionen nicht modelliert (der
    Sonderfall muss VOR dem delta-Guard greifen).

    v2.3.0 (S308): die Bedingung ``kind == "energy_at_least"`` ist RAUS. Sie
    koppelte den Sonderfall an die Subsistenz-Lage — gebaut am Fall Socket-hand
    (Diplomat, Schwelle 20k, permanent Subsistenz). Ein SOLVENTER Feldloser
    (Comet-hand: scientist, Schwelle 2.000, Guthaben 11.449, decay-frei unterm
    Floor) erreicht Subsistenz nie, sein Ziel ist ``field_count_at_least`` —
    der Sonderfall griff nicht, start_mission bekam 0.0 und verlor die
    Abstimmung 0.20:0.15 gegen market_list. Ergebnis: minütliches Listing statt
    Rueckkehr ins Spiel. Die S306-Founder-Direktive ist feldlos-basiert („wer
    KEIN Feld hat, klaert auf, egal welche Persona — Besitz ist
    Existenzgrundlage"), nicht subsistenz-basiert.

    Die Founder-Ordnung „freier Slot schlaegt Erobern" (S307: 0.9 <
    create_field) steht dafuer jetzt STRUKTURELL hier: ist ``create_field``
    gueltig (Slot frei + bezahlbar), schweigt der Sonderfall — der
    create_field-Pfad gewinnt dann ohne Wettrennen der Persona-Biases. Als
    Score-Duell waere die Ordnung persona-abhaengig gekippt (scientist:
    create_field-Bias −0.2 gegen start_mission +0.15 haette Erobern ueber den
    freien Slot gestellt).
    """
    return (
        action == "start_mission"
        and bool(params)
        and len(_fields(state)) == 0
        and not is_valid(state, "create_field")
    )


def score_action(
    state: GameState, action: str, params: dict[str, Any], goal_metric: dict[str, Any]
) -> float:
    """Wie sehr reduziert die Action die Distanz zum Goal? [0, 1], hoeher = besser.

    Duenner Flur: der Feldlos-Sonderfall greift VOR der delta-Logik
    (_predict_delta modelliert Missionen nicht); alles andere entscheidet
    ``_score_gegen_ziel``.
    """
    if _feldloser_missions_zug(state, action, params, goal_metric):
        return 0.9  # v2.2.1: < 1.0 (create_field) — freier Slot schlaegt Erobern
    return _score_gegen_ziel(state, action, params, goal_metric)


def _score_energie_ziel(
    state: GameState, action: str, delta: dict[str, Any], goal_metric: dict[str, Any]
) -> float:
    target = float(goal_metric.get("target", 0))
    gap = max(0.0, target - _energy(state))
    if gap == 0:
        return 0.1  # Goal erreicht, Action irrelevant aber kein negativ
    # Sonderfall: 0 Fields + create_field ist EINZIGE sustainable Income-Quelle.
    # Ohne Field gibt es kein Conway-Income, market_list ist einmaliger Boost,
    # danach wieder im selben State. Bootstrap braucht create_field absolut.
    if action == "create_field" and len(_fields(state)) == 0:
        return 1.0
    # Direktes Energy-Plus; 0.5 weil market_list ungewisser Verkauf
    e_delta = delta.get("energy", 0.0) + delta.get("energy_listed", 0.0) * 0.5
    return max(0.0, min(1.0, e_delta / gap))


def _score_zellen_ziel(
    state: GameState, action: str, delta: dict[str, Any], goal_metric: dict[str, Any]
) -> float:
    target = float(goal_metric.get("target", 100))
    fields = _fields(state)
    if not fields:
        return 0.5 if action == "create_field" else 0.0
    current = sum(getattr(f, "active_cell_count", 0) or 0 for f in fields) / len(fields)
    gap = max(0.0, target - current)
    if gap == 0:
        return 0.1
    # Direction-based scoring: jede Action die in richtige Richtung wirkt
    # bekommt einen Mindest-Score, auch bei geringer Magnitude. Sonst
    # wird bei vielen Fields der Cell-Anstieg pro place_cells (1/N) zu klein
    # bewertet und Pet würde nie Cells nachfüllen (S171 Pulsar-eye-Befund).
    avg_cells_delta = delta.get("avg_cells", 0.0)
    if avg_cells_delta > 0:
        # Right-direction action — base score 0.7, plus magnitude-Bonus.
        return 0.7 + min(0.3, avg_cells_delta / gap)
    return 0.0  # Wrong direction oder kein Effekt


def _score_bestands_ziele(
    state: GameState, action: str, delta: dict[str, Any], kind: str, goal_metric: dict[str, Any]
) -> float:
    """Die kleinen Ziel-Arten: Felder, Evolves, Muster, Vertraege, Inventar, Markt."""
    if kind == "field_count_at_least":
        gap = max(0, int(goal_metric.get("target", 1)) - len(_fields(state)))
        if gap == 0:
            return 0.1
        return 0.8 if delta.get("field_count", 0) > 0 else 0.0
    if kind == "evolved_fields_at_least":
        return 1.0 if delta.get("evolved_fields", 0) > 0 else 0.0
    if kind == "patterns_established":
        return 0.8 if delta.get("patterns_established", 0) > 0 else 0.0
    if kind == "active_contracts_at_least":
        return 1.0 if delta.get("active_contracts", 0) > 0 else 0.0
    if kind == "all_fields_min_cells":
        # place_cells auf das Field mit den wenigsten Cells reduziert die Distanz
        if action == "place_cells":
            fewest = _fewest_cells_field(state)
            if fewest:
                current = getattr(fewest, "active_cell_count", 0) or 0
                if current < float(goal_metric.get("target", 30)):
                    return 0.9
        return 0.0
    if kind == "fields_use_inventory":
        return 0.8 if action in ("create_field", "place_cells") else 0.0
    if kind == "energy_growth_via_market":
        return 0.8 if action in ("market_buy", "market_list") else 0.0
    return 0.0


def _score_gegen_ziel(
    state: GameState, action: str, params: dict[str, Any], goal_metric: dict[str, Any]
) -> float:
    """Dispatcher der Ziel-Metriken — Logik unveraendert seit v2.0.2, nur
    entlang der kind-Naehte zerlegt (§11.2)."""
    delta = _predict_delta(state, action, params)
    if not delta:
        return 0.0
    kind = goal_metric.get("kind", "")
    if kind == "energy_at_least":
        return _score_energie_ziel(state, action, delta, goal_metric)
    if kind == "avg_cells_at_least":
        return _score_zellen_ziel(state, action, delta, goal_metric)
    return _score_bestands_ziele(state, action, delta, kind, goal_metric)


# --- Decision-Pipeline -------------------------------------------------------


def _decide_pending_contract(state: GameState, persona: str) -> tuple[str, dict[str, Any]] | None:
    """S204 — wenn pending contract addressed an mich, entscheide accept/reject.

    Schaut auf state.pending_contracts (vom SDK in state-poll geliefert).
    Returnt None wenn keine Entscheidung anliegt (Tree-Decider macht normalen Pfad).
    """
    pending = getattr(state, "pending_contracts", None) or []
    if not pending:
        return None
    bias = PERSONA_CONTRACT_BIAS.get(persona, {})
    for c in pending:
        ctype = c.get("contract_type") if isinstance(c, dict) else getattr(c, "contract_type", None)
        cid = c.get("contract_id") if isinstance(c, dict) else getattr(c, "contract_id", None)
        if not ctype or not cid:
            continue
        decision = bias.get(ctype)
        if decision == "accept":
            return ("accept_contract", {"contract_id": str(cid), "escrow_amount": 0.0})
        if decision == "reject":
            return ("reject_contract", {"contract_id": str(cid)})
    return None


def _score_pool(
    state: GameState,
    persona: str,
    action_pool: tuple[str, ...],
    goal_metric: dict[str, Any],
    bias_map: dict[str, float],
    compass_modifier: dict[str, float],
    blocked: frozenset[str],
) -> dict[str, tuple[float, dict[str, Any]]]:
    """Validity + Score über den Aktions-Pool (Basis + Persona- + Compass-Bias)."""
    scores: dict[str, tuple[float, dict[str, Any]]] = {}
    for action in action_pool:
        if action not in VALID_ACTIONS:
            continue
        if action in blocked:
            continue  # v2.1.0 Backoff — der Loop hat sie gesperrt
        if not is_valid(state, action):
            continue
        params = resolve_action_params(state, action, persona)
        base = score_action(state, action, params, goal_metric)
        persona_b = bias_map.get(action, 0.0)
        compass_b = compass_modifier.get(action, 0.0)
        final = base + persona_b + compass_b
        scores[action] = (final, params)
    return scores


class TreeDecider:
    """GOBT-Pattern decider: Subsistenz-Check + Persona-Charakter-Cycle.

    v2.1.0 (S297): ``decide`` nimmt optional ``blocked`` — Aktionen, die der
    aufrufende Loop nach wiederholten identischen Fehlschlägen vorübergehend
    gesperrt hat (Backoff lebt im Loop, der Decider bleibt zustandslos).
    """

    name: str = "tree"
    version: str = "2.3.0"

    async def decide(
        self, state: GameState, blocked: frozenset[str] = frozenset()
    ) -> tuple[str, dict[str, Any]]:
        # Critical-Energy → wait (Sink-Schutz, vor allen Layern)
        if _energy(state) < CRITICAL_ENERGY:
            return ("wait", {})

        persona = (getattr(state, "persona_type", None) or "scientist").lower()
        if persona not in PERSONA_ACTION_POOLS:
            persona = "scientist"  # default

        # S204 Layer 0 — Pending Contracts haben Vorrang (Founder-Direktive
        # "ALLE dürfen ALLES vereinbaren"). Pro decide()-Call max 1 Vertrags-
        # Entscheidung, dann normaler Tree-Pfad.
        contract_decision = _decide_pending_contract(state, persona)
        if contract_decision is not None:
            return contract_decision

        compass = getattr(state, "compass_preset", None)

        # Layer 1: Subsistenz-Check
        if needs_subsistence(state, persona):
            action_pool: tuple[str, ...] = SUBSISTENCE_POOL
            goal_metric = {
                "kind": "energy_at_least",
                "target": subsistence_threshold(persona, state) * 1.5,
            }
            bias_map = SUBSISTENCE_BIAS
        else:
            # Layer 2: Persona-Charakter
            action_pool = PERSONA_ACTION_POOLS[persona]
            goal_metric = persona_current_goal(state, persona)
            bias_map = PERSONA_ACTION_BIAS.get(persona, {})

        # Compass-Modifier (additiv)
        compass_modifier = COMPASS_BIAS.get(compass or "autonomous", {})

        scores = _score_pool(
            state, persona, action_pool, goal_metric, bias_map, compass_modifier, blocked
        )

        if not scores:
            return ("wait", {})

        # Argmax
        best = max(scores.keys(), key=lambda a: scores[a][0])
        action, params = best, scores[best][1]

        if action not in VALID_ACTIONS:
            logger.warning("v2.0.0 produced invalid action %r → wait", action)
            return ("wait", {})

        return action, params

    async def healthcheck(self) -> bool:
        return True
