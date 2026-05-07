"""TreeDecider — rule-based decision tree, deterministic, no inference.

VENDORED from ``cosmergon-decider-tree`` v1.0.0 (private cosmergon repo,
``research/decider-cluster/decider-tree/``). Source-of-truth lives there.
This copy lets the Pet stay installable from a single
``pip install cosmergon-pet`` without an additional dep that has its own
release cadence. When the upstream changes, copy the file again and
bump the Pet's MINOR version. Pure-Python rule logic, no model file, no
inference — vendoring is cheap.

Quelle:
  - docs/konzepte/konzept-default-entscheidungsbaum-api-agents.md §3
    (Basis-Baum + Persona-spezifisch + Compass-Modulation)
  - Pet S165 L1 _PERSONA_GUIDANCE conditional sequences als
    Inspirations-Schwelle (gleiche Persona-Pfade, deterministisch
    statt prompt-conditional).

Decision-Pipeline:

    state (GameState)
        │
        ├─ persona = state.persona_type or "scientist"
        ▼
    PERSONA_TREES[persona] (list of (condition, action_fn) tuples)
        │
        ├─ first matching condition wins
        ▼
    (action, params)

Compass-Modulation (state.compass_preset) tunet einzelne
Branch-Schwellen (z.B. warrior+consolidate hebt eigene-Felder-Pflege),
optional, fällt durch wenn nicht gesetzt.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from cosmergon_agent.state import GameState

logger = logging.getLogger(__name__)

VALID_ACTIONS: frozenset[str] = frozenset(
    {
        "place_cells",
        "evolve",
        "create_field",
        "transfer_energy",
        "market_list",
        "market_buy",
        "propose_contract",
        "wait",
    }
)

# --- Konditions-Predikate ----------------------------------------------------
# Alle Predikate sind pure und nehmen GameState. Sie müssen robust gegen
# fehlende Felder sein (state-Schema kann variieren), daher häufig
# ``getattr(state, name, default)``.


def _energy(state: GameState) -> float:
    return float(getattr(state, "energy", 0) or 0)


def _fields(state: GameState) -> list[Any]:
    return list(getattr(state, "fields", []) or [])


def _own_fields_count(state: GameState) -> int:
    return len(_fields(state))


def _has_universe_cube(state: GameState) -> bool:
    cubes = list(getattr(state, "universe_cubes", []) or [])
    return len(cubes) > 0


def _has_evolvable_field(state: GameState) -> bool:
    """Mirrors Pet face.py::_find_evolvable_field — full can-evolve gate."""
    REIFE_THRESHOLDS = {2: 100, 3: 500, 4: 2000, 5: 10000}
    EVOLUTION_COST = {1: 1000, 2: 5000, 3: 25000, 4: 125000}
    TYPE_FOR_TIER = {2: "oscillator", 3: "spaceship", 4: "gun", 5: "breeder"}

    energy = _energy(state)
    for f in _fields(state):
        tier = getattr(f, "entity_tier", None) or 0
        if not isinstance(tier, int) or tier <= 0 or tier >= 5:
            continue
        next_tier = tier + 1
        reife = getattr(f, "reife_score", None) or 0
        if reife < REIFE_THRESHOLDS.get(next_tier, 999_999):
            continue
        required_type = TYPE_FOR_TIER.get(next_tier)
        if required_type and getattr(f, "entity_type", None) != required_type:
            continue
        cost = EVOLUTION_COST.get(tier, 0)
        if energy < cost:
            continue
        return True
    return False


def _cheapest_evolvable_field(state: GameState) -> Any | None:
    REIFE_THRESHOLDS = {2: 100, 3: 500, 4: 2000, 5: 10000}
    EVOLUTION_COST = {1: 1000, 2: 5000, 3: 25000, 4: 125000}
    TYPE_FOR_TIER = {2: "oscillator", 3: "spaceship", 4: "gun", 5: "breeder"}
    energy = _energy(state)
    eligible = []
    for f in _fields(state):
        tier = getattr(f, "entity_tier", None) or 0
        if not isinstance(tier, int) or tier <= 0 or tier >= 5:
            continue
        next_tier = tier + 1
        reife = getattr(f, "reife_score", None) or 0
        if reife < REIFE_THRESHOLDS.get(next_tier, 999_999):
            continue
        required_type = TYPE_FOR_TIER.get(next_tier)
        if required_type and getattr(f, "entity_type", None) != required_type:
            continue
        cost = EVOLUTION_COST.get(tier, 0)
        if energy < cost:
            continue
        eligible.append((cost, f))
    if not eligible:
        return None
    eligible.sort(key=lambda p: p[0])
    return eligible[0][1]


def _empty_field(state: GameState) -> Any | None:
    """Field mit aktiver_zellzahl = 0 → braucht place_cells."""
    for f in _fields(state):
        if (getattr(f, "active_cell_count", 0) or 0) == 0:
            return f
    return None


def _fewest_cells_field(state: GameState) -> Any | None:
    fs = _fields(state)
    if not fs:
        return None
    return min(fs, key=lambda f: getattr(f, "active_cell_count", 0) or 0)


def _affordable_preset(state: GameState) -> str:
    """Cheapest preset the agent can afford; 'block' as default."""
    energy = _energy(state)
    presets = [
        ("block", 5),
        ("blinker", 10),
        ("toad", 50),
        ("glider", 200),
        ("r_pentomino", 200),
    ]
    for name, cost in presets:
        if energy >= cost:
            cheapest = name
        else:
            break
    return cheapest if "cheapest" in dir() else "block"


def _any_field_below_cells(state: GameState, threshold: int) -> Any | None:
    for f in _fields(state):
        if (getattr(f, "active_cell_count", 0) or 0) < threshold:
            return f
    return None


def _cheapest_buyable(state: GameState, max_price: float) -> Any | None:
    wb = getattr(state, "world_briefing", None)
    market = getattr(wb, "market", None) if wb is not None else None
    buyable = list(getattr(market, "buyable", ()) or [])
    energy = _energy(state)
    candidates = [
        b
        for b in buyable
        if (getattr(b, "price_energy", 1e18) or 1e18) <= max_price
        and (getattr(b, "price_energy", 1e18) or 1e18) <= energy
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda b: getattr(b, "price_energy", 1e18))


def _market_list_offered(state: GameState, min_energy: float) -> bool:
    return _energy(state) >= min_energy


def _contract_target(state: GameState) -> Any | None:
    wb = getattr(state, "world_briefing", None)
    targets = list(getattr(wb, "contract_targets", ()) or []) if wb is not None else []
    return targets[0] if targets else None


# --- Branch-Konstruktoren ----------------------------------------------------

Branch = tuple[Callable[[GameState], bool], Callable[[GameState], tuple[str, dict[str, Any]]]]


def _act_place_cells_fewest(state: GameState) -> tuple[str, dict[str, Any]]:
    f = _fewest_cells_field(state)
    if f is None:
        return ("wait", {})
    return ("place_cells", {"field_id": str(f.id), "preset": _affordable_preset(state)})


def _act_place_cells_empty(state: GameState) -> tuple[str, dict[str, Any]]:
    f = _empty_field(state) or _fewest_cells_field(state)
    if f is None:
        return ("wait", {})
    return ("place_cells", {"field_id": str(f.id), "preset": "block"})


def _act_evolve(state: GameState) -> tuple[str, dict[str, Any]]:
    f = _cheapest_evolvable_field(state)
    if f is None:
        return ("wait", {})
    return ("evolve", {"field_id": str(f.id)})


def _act_create_field(state: GameState) -> tuple[str, dict[str, Any]]:
    cubes = list(getattr(state, "universe_cubes", []) or [])
    if not cubes:
        return ("wait", {})
    return ("create_field", {"cube_id": str(cubes[0].id)})


def _act_market_buy_under(price: float):
    def inner(state: GameState) -> tuple[str, dict[str, Any]]:
        b = _cheapest_buyable(state, price)
        if b is None:
            return ("wait", {})
        return ("market_buy", {"listing_id": str(b.listing_id)})

    return inner


def _act_market_list(price: int):
    def inner(state: GameState) -> tuple[str, dict[str, Any]]:
        return ("market_list", {"price_energy": price})

    return inner


def _act_propose_non_aggression(state: GameState) -> tuple[str, dict[str, Any]]:
    t = _contract_target(state)
    if t is None:
        return ("wait", {})
    return (
        "propose_contract",
        {
            "to_player_id": str(t.player_id),
            "contract_type": "non_aggression",
            "terms": {"duration_ticks": 100},
            "escrow_amount": 0,
        },
    )


def _act_propose_trade_agreement(state: GameState) -> tuple[str, dict[str, Any]]:
    t = _contract_target(state)
    if t is None:
        return ("wait", {})
    return (
        "propose_contract",
        {
            "to_player_id": str(t.player_id),
            "contract_type": "trade_agreement",
            "terms": {"duration_ticks": 100},
            "escrow_amount": 0,
        },
    )


def _act_wait(state: GameState) -> tuple[str, dict[str, Any]]:
    return ("wait", {})


# --- Basis-Baum (Survival → Wachstum) ----------------------------------------

CRITICAL_ENERGY = 100.0  # Sink-Schutz, Konzept §3.1


def _can_afford_field(state: GameState) -> bool:
    """Read backend-truth from `state.available_actions["create_field"]`.

    Backend `_build_action_availability` (agent_game.py:2595+) computes
    `can_afford` against the live hot-config `FIELD_COST_BASE`. Bei 0
    owned fields ist next_cost=0 → True (first field free). S168:
    vorherige Tree-Konstante `FIELD_COST_BASE = 5_000.0` war ein Drift-
    Bug, der den 0→1-Übergang für jeden Agent <5k E strukturell
    blockierte; SDK ≥ 0.13.1 reicht das Backend-Feld jetzt durch
    (`state.available_actions["create_field"]["can_afford"]`).
    """
    actions = getattr(state, "available_actions", None) or {}
    create = actions.get("create_field") if isinstance(actions, dict) else None
    if isinstance(create, dict) and "can_afford" in create:
        return bool(create["can_afford"])
    return False  # Conservative: alte Backends ohne available_actions → Branch greift nicht.


BASE_TREE: list[Branch] = [
    # 1. Critical-Energy → wait (Sink-Schutz)
    (lambda s: _energy(s) < CRITICAL_ENERGY, _act_wait),
    # 2. Keine eigenen Felder + Field bezahlbar → create_field
    #    S168: backend-getriebene cost-prüfung statt hardcode. Greift
    #    insbesondere bei 0 owned (next_field=0, "first field free").
    (
        lambda s: _own_fields_count(s) == 0 and _can_afford_field(s) and _has_universe_cube(s),
        _act_create_field,
    ),
    # 3. Empty field → place_cells block (Reanimation)
    (lambda s: _empty_field(s) is not None, _act_place_cells_empty),
    # 4. Evolvable field → evolve
    (lambda s: _has_evolvable_field(s), _act_evolve),
    # 5. Energy >= 30k AND universe-cube → create_field (Wachstum)
    (
        lambda s: _energy(s) >= 30_000 and _has_universe_cube(s),
        _act_create_field,
    ),
    # 6. Energy >= 100k AND cheap listing → market_buy
    (
        lambda s: _energy(s) >= 100_000 and _cheapest_buyable(s, 2_000) is not None,
        _act_market_buy_under(2_000),
    ),
    # 7. Energy >= 1500 → market_list (mid price-tier)
    (lambda s: _market_list_offered(s, 1_500), _act_market_list(450)),
    # 8. Fallback: place_cells fewest cells
    (lambda s: _own_fields_count(s) > 0, _act_place_cells_fewest),
    # 9. Sonst: wait
    (lambda s: True, _act_wait),
]


# --- Persona-spezifische Bäume ------------------------------------------------
# Jede Persona hat einen eigenen Branch-Order. Pattern: prepend
# Persona-Kerngeschäft-Branches an Basis-Baum, sodass diese zuerst
# evaluiert werden. Critical-Energy + Empty-Field bleiben Top-Branches
# in jedem Tree (Survival universal).


def _persona_tree(persona_branches: list[Branch]) -> list[Branch]:
    """Persona-Branches kommen zwischen Survival und Wachstum-Default-Tree."""
    survival = BASE_TREE[:3]  # critical-energy + 0-fields + empty-field
    fallback = BASE_TREE[7:]  # fewest-cells + wait
    return survival + persona_branches + fallback


SCIENTIST_BRANCHES: list[Branch] = [
    # scientist: evolve > create_field > market_buy_blueprint > market_list_publish
    (lambda s: _has_evolvable_field(s), _act_evolve),
    (lambda s: _energy(s) >= 100_000 and _cheapest_buyable(s, 2_000), _act_market_buy_under(2_000)),
    (lambda s: _energy(s) >= 30_000 and _has_universe_cube(s), _act_create_field),
    (lambda s: _energy(s) >= 100_000 and _market_list_offered(s, 100_000), _act_market_list(450)),
    (
        lambda s: _energy(s) >= 50_000 and _contract_target(s) is not None,
        _act_propose_trade_agreement,
    ),
]

WARRIOR_BRANCHES: list[Branch] = [
    # warrior: place_cells aggressive (close-the-gap) > evolve > create_field > market_buy edge
    (lambda s: _any_field_below_cells(s, 30) is not None, _act_place_cells_fewest),
    (lambda s: _has_evolvable_field(s), _act_evolve),
    (lambda s: _energy(s) >= 5_000 and _has_universe_cube(s), _act_create_field),
    (lambda s: _energy(s) >= 100_000 and _cheapest_buyable(s, 2_000), _act_market_buy_under(2_000)),
    (
        lambda s: _energy(s) >= 50_000 and _contract_target(s) is not None,
        _act_propose_non_aggression,
    ),
]

EXPANSIONIST_BRANCHES: list[Branch] = [
    # expansionist: create_field maximal > market_buy cheap_acquisition > place_cells bootstrap > evolve
    (lambda s: _energy(s) >= 5_000 and _has_universe_cube(s), _act_create_field),
    (lambda s: _energy(s) >= 100_000 and _cheapest_buyable(s, 2_000), _act_market_buy_under(2_000)),
    (lambda s: _any_field_below_cells(s, 30) is not None, _act_place_cells_fewest),
    (lambda s: _has_evolvable_field(s), _act_evolve),
    (
        lambda s: _energy(s) >= 50_000 and _contract_target(s) is not None,
        _act_propose_non_aggression,
    ),
]

TRADER_BRANCHES: list[Branch] = [
    # trader: market_buy primary > market_list monetise > evolve > create_field
    (
        lambda s: _energy(s) >= 100_000 and _cheapest_buyable(s, _energy(s) * 0.1),
        _act_market_buy_under(1e9),
    ),
    (lambda s: _market_list_offered(s, 30_000), _act_market_list(450)),
    (
        lambda s: _energy(s) >= 30_000 and _contract_target(s) is not None,
        _act_propose_trade_agreement,
    ),
    (lambda s: _has_evolvable_field(s), _act_evolve),
    (lambda s: _energy(s) >= 10_000 and _has_universe_cube(s), _act_create_field),
]

DIPLOMAT_BRANCHES: list[Branch] = [
    # diplomat: propose_contract prime move > market_buy goodwill > market_list relationship-build
    (
        lambda s: _energy(s) >= 10_000 and _contract_target(s) is not None,
        _act_propose_non_aggression,
    ),
    (lambda s: _cheapest_buyable(s, 1_500), _act_market_buy_under(1_500)),
    (lambda s: _market_list_offered(s, 30_000), _act_market_list(450)),
    (lambda s: _has_evolvable_field(s), _act_evolve),
    (lambda s: _energy(s) >= 5_000 and _has_universe_cube(s), _act_create_field),
]

FARMER_BRANCHES: list[Branch] = [
    # farmer: top-up (place_cells <50) > market_list surplus > evolve > market_buy cheap
    (lambda s: _any_field_below_cells(s, 50) is not None, _act_place_cells_fewest),
    (lambda s: _market_list_offered(s, 50_000), _act_market_list(450)),
    (lambda s: _has_evolvable_field(s), _act_evolve),
    (lambda s: _cheapest_buyable(s, 500), _act_market_buy_under(500)),
    (lambda s: _energy(s) >= 10_000 and _has_universe_cube(s), _act_create_field),
    (
        lambda s: _energy(s) >= 80_000 and _contract_target(s) is not None,
        _act_propose_non_aggression,
    ),
]


PERSONA_TREES: dict[str, list[Branch]] = {
    "scientist": _persona_tree(SCIENTIST_BRANCHES),
    "warrior": _persona_tree(WARRIOR_BRANCHES),
    "expansionist": _persona_tree(EXPANSIONIST_BRANCHES),
    "trader": _persona_tree(TRADER_BRANCHES),
    "diplomat": _persona_tree(DIPLOMAT_BRANCHES),
    "farmer": _persona_tree(FARMER_BRANCHES),
}


# --- Compass-Modulation (optional Override-Hook) -----------------------------


def _compass_modulate(
    action: str,
    params: dict[str, Any],
    compass: str | None,
    state: GameState,
) -> tuple[str, dict[str, Any]]:
    """Compass-Override: einzelne Aktionen können je nach Compass
    nachgeführt werden. MVP: leichte Anpassungen, kein voll-blockierender
    Override.

    Konzept §3.3:
      warrior+consolidate → eigene Felder bevorzugen → wenn create_field,
        umstellen auf place_cells fewest
      diplomat+defend → propose_contract non_aggression erzwingen
      farmer+explore → create_field früher freischalten (heute kein
        Override-Bedarf, fällt durch)
    """
    if not compass:
        return action, params

    if action == "create_field" and compass == "consolidate":
        # consolidate: bevorzuge eigene Felder pflegen statt neuen anlegen
        f = _fewest_cells_field(state)
        if f is not None:
            return ("place_cells", {"field_id": str(f.id), "preset": _affordable_preset(state)})

    if action == "propose_contract" and compass == "defend":
        # defend: erzwinge non_aggression
        if params.get("contract_type") == "trade_agreement":
            new_params = dict(params)
            new_params["contract_type"] = "non_aggression"
            return action, new_params

    return action, params


# --- Decider-Klasse ---------------------------------------------------------


class TreeDecider:
    """Rule-based decision tree decider."""

    name: str = "tree"
    version: str = "1.0.0"

    async def decide(self, state: GameState) -> tuple[str, dict[str, Any]]:
        persona = (getattr(state, "persona_type", None) or "scientist").lower()
        tree = PERSONA_TREES.get(persona, PERSONA_TREES["scientist"])
        for condition, action_fn in tree:
            try:
                if condition(state):
                    action, params = action_fn(state)
                    compass = getattr(state, "compass_preset", None)
                    if compass:
                        action, params = _compass_modulate(action, params, compass, state)
                    if action not in VALID_ACTIONS:
                        # Defensive: should never happen with our action_fns,
                        # but defend against future regressions.
                        logger.warning("tree produced invalid action %r → wait", action)
                        return ("wait", {})
                    return action, params
            except Exception as e:
                logger.warning("tree branch errored: %s — skipping", e)
                continue
        return ("wait", {})

    async def healthcheck(self) -> bool:
        return True
