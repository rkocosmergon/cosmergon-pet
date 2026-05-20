"""TreeDecider v2.0.2 — Subsistenz + Persona-Charakter (GOBT-Pattern).

VENDORED from ``cosmergon-decider-tree`` v2.0.2 (private cosmergon repo,
``research/decider-cluster/decider-tree/``). Source-of-truth lives there.

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
    return list(getattr(state, "universe_cubes", []) or [])


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
        # Existiert ein Field das evolve-eligible ist?
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

    if action == "market_buy":
        persona = (getattr(state, "persona_type", None) or "scientist").lower()
        allowed = PERSONA_BUYABLE_TYPES.get(persona, ("cube", "field"))
        energy = _energy(state)
        for b in _market_buyable(state):
            if allowed is not None:
                item_type = getattr(b, "item_type", None)
                if item_type not in allowed:
                    continue
            price = getattr(b, "price_energy", None)
            if price is None:
                continue
            try:
                if float(price) <= energy:
                    return True
            except (TypeError, ValueError):
                continue
        return False

    if action == "market_list":
        # Pet braucht etwas zum Listen + minimum-Energy für list-fee
        # Vereinfacht: list_threshold persona-spezifisch, hier minimal 1500
        return _energy(state) >= 1_500

    if action == "propose_contract":
        return len(_contract_targets(state)) > 0 and _energy(state) >= 5_000

    if action == "transfer_energy":
        return False  # nicht in v2.0.0-Action-Pool

    return False


# --- Action-Parameter-Resolver -----------------------------------------------


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
        b = _cheapest_buyable(state, persona)
        return {"listing_id": str(b.listing_id)} if b else {}

    if action == "market_list":
        # Persona-spezifischer Listenpreis (default 450)
        prices = {
            "trader": 500,
            "scientist": 450,
            "warrior": 400,
            "expansionist": 400,
            "diplomat": 450,
            "farmer": 450,
        }
        return {"price_energy": prices.get(persona, 450)}

    if action == "propose_contract":
        targets = _contract_targets(state)
        if not targets:
            return {}
        target = targets[0]
        contract_types = {
            "scientist": "research_agreement",
            "trader": "trade_agreement",
            "warrior": "non_aggression",
            "diplomat": "non_aggression",
            "farmer": "trade_agreement",
            "expansionist": "non_aggression",
        }
        return {
            "to_player_id": str(target.player_id),
            "contract_type": contract_types.get(persona, "non_aggression"),
            # Backend-Validator (contract_manager.validate_terms) erwartet
            # API-Term-Key 'duration' (nicht 'duration_ticks' — das ist nur die
            # ORM-Column, models/contract.py:94). Verifiziert 2026-05-09 nach
            # Socket-hand 0/99 success-Empirie auf RPi 4 (S178).
            "terms": {"duration": 100},
            "escrow_amount": 0,
        }

    return {}


# --- Predict-Delta-Funktionen (was ändert die Action am State?) --------------


def _predict_delta(state: GameState, action: str, params: dict[str, Any]) -> dict[str, float]:
    """Schätzt State-Delta für die Action. Wird vom Score genutzt um
    Goal-Distance-Reduktion zu messen."""
    n_fields = len(_fields(state))

    if action == "wait":
        return {}

    if action == "create_field":
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

    if action == "place_cells":
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

    if action == "evolve":
        # Tier-Aufstieg eines Fields
        f = _cheapest_evolvable_field(state)
        if f is None:
            return {}
        tier = getattr(f, "entity_tier", 1) or 1
        cost = EVOLUTION_COST_BY_TIER.get(tier, 1_000)
        return {"energy": -cost, "evolved_fields": +1}

    if action == "market_buy":
        b = _cheapest_buyable(state, (getattr(state, "persona_type", None) or "scientist").lower())
        if b is None:
            return {}
        price = getattr(b, "price_energy", 0) or 0
        item_type = getattr(b, "item_type", None)
        return {
            "energy": -float(price),
            "inventory_growth": +1,
            "is_cube_or_field": 1.0 if item_type in ("cube", "field") else 0.0,
        }

    if action == "market_list":
        # Annahme: list-fee marginal, Verkauf ist ungewiss aber positiv
        list_price = params.get("price_energy", 450)
        return {"energy_listed": +float(list_price), "energy": -10.0}  # listing-fee

    if action == "propose_contract":
        return {"energy": -float(params.get("escrow_amount", 0) or 0), "active_contracts": +1}

    return {}


# --- Score-Funktion (generisch, mit Goal-Metric) -----------------------------


def score_action(
    state: GameState, action: str, params: dict[str, Any], goal_metric: dict[str, Any]
) -> float:
    """Wie sehr reduziert die Action die Distanz zum Goal?
    Returns float in [0, 1]. Höher = besser."""
    delta = _predict_delta(state, action, params)
    if not delta:
        return 0.0

    kind = goal_metric.get("kind", "")

    if kind == "energy_at_least":
        target = float(goal_metric.get("target", 0))
        current = _energy(state)
        gap = max(0.0, target - current)
        if gap == 0:
            return 0.1  # Goal erreicht, Action irrelevant aber kein negativ
        # Sonderfall: 0 Fields + create_field ist EINZIGE sustainable Income-Quelle.
        # Ohne Field gibt es kein Conway-Income, market_list ist einmaliger Boost,
        # danach wieder im selben State. Bootstrap braucht create_field absolut.
        if action == "create_field" and len(_fields(state)) == 0:
            return 1.0
        # Direktes Energy-Plus
        e_delta = delta.get("energy", 0.0) + delta.get("energy_listed", 0.0) * 0.5
        # 0.5 weil market_list ungewisser Verkauf
        return max(0.0, min(1.0, e_delta / gap))

    if kind == "avg_cells_at_least":
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
            magnitude_bonus = min(0.3, avg_cells_delta / gap)
            return 0.7 + magnitude_bonus
        elif avg_cells_delta < 0:
            return 0.0  # Wrong direction (z.B. create_field reduziert avg_cells)
        return 0.0  # No effect

    if kind == "field_count_at_least":
        target = int(goal_metric.get("target", 1))
        current = len(_fields(state))
        gap = max(0, target - current)
        if gap == 0:
            return 0.1
        # Direction-based: create_field bringt +1 Field, andere 0
        if delta.get("field_count", 0) > 0:
            return 0.8
        return 0.0

    if kind == "evolved_fields_at_least":
        # Evolve-Action ist direkt zielführend
        return 1.0 if delta.get("evolved_fields", 0) > 0 else 0.0

    if kind == "patterns_established":
        return 0.8 if delta.get("patterns_established", 0) > 0 else 0.0

    if kind == "active_contracts_at_least":
        target = int(goal_metric.get("target", 1))
        # Wir kennen aktuelle contract-count nicht direkt; approximieren mit delta
        return 1.0 if delta.get("active_contracts", 0) > 0 else 0.0

    if kind == "all_fields_min_cells":
        target = float(goal_metric.get("target", 30))
        # place_cells auf das Field mit den wenigsten Cells reduziert die Distanz
        if action == "place_cells":
            fewest = _fewest_cells_field(state)
            if fewest:
                current = getattr(fewest, "active_cell_count", 0) or 0
                if current < target:
                    return 0.9
        return 0.0

    if kind == "fields_use_inventory":
        # Trader-Inventar-Use: create_field oder place_cells = gut
        if action in ("create_field", "place_cells"):
            return 0.8
        return 0.0

    if kind == "energy_growth_via_market":
        # Trader-Markt-Spread: market_buy + market_list = gut
        if action in ("market_buy", "market_list"):
            return 0.8
        return 0.0

    return 0.0


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


class TreeDecider:
    """GOBT-Pattern decider: Subsistenz-Check + Persona-Charakter-Cycle."""

    name: str = "tree"
    version: str = "2.0.2"

    async def decide(self, state: GameState) -> tuple[str, dict[str, Any]]:
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

        # Validity + Score
        scores: dict[str, tuple[float, dict[str, Any]]] = {}
        for action in action_pool:
            if action not in VALID_ACTIONS:
                continue
            if not is_valid(state, action):
                continue
            params = resolve_action_params(state, action, persona)
            base = score_action(state, action, params, goal_metric)
            persona_b = bias_map.get(action, 0.0)
            compass_b = compass_modifier.get(action, 0.0)
            final = base + persona_b + compass_b
            scores[action] = (final, params)

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
