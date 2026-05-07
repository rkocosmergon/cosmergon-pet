"""TreeDecider — rule-based decision tree, deterministic, no inference.

VENDORED from ``cosmergon-decider-tree`` v1.1.1 (private cosmergon repo,
``research/decider-cluster/decider-tree/``). Source-of-truth lives there.
This copy lets the Pet stay installable from a single
``pip install cosmergon-pet`` without an additional dep that has its own
release cadence. When the upstream changes, copy the file again and
bump the Pet's MINOR version. Pure-Python rule logic, no model file, no
inference — vendoring is cheap.

v1.1.1 changes (vs. v1.1.0 in Pet 0.1.30):
  - Anti-Hoarding cube-cap on market_buy. S170-finding: comet-hand kept
    buying cheap blueprints permanently because the scientist[1] branch
    matched constantly at rich-state. Cap=5 unused cubes now blocks
    further market_buy in all personas, falling through to the next
    branch (typically create_field), which uses cubes up.

v1.1.0 changes (vs. v1.0.0 in Pet 0.1.29):
  - Pattern-Tier-aware preset selection (scientist/expansionist/farmer
    pick `blinker` for evolve-prep, others keep `block`)
  - Persona-Branches now have priority over empty_field-Refill (prevents
    rich-state survival tunnel-vision — comet-hand S170 finding)
  - Compass-Modulation extended (grow / cooperate / attack / explore)

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


def _cube_count(state: GameState) -> int:
    return len(list(getattr(state, "universe_cubes", []) or []))


# v1.1.1 — Anti-Hoarding cap auf market_buy.
# S170-Befund (comet-hand): scientist matched permanent market_buy weil Branch [1]
# konstant True ist bei rich-state + cheap blueprints. Pet sammelte 12+ cubes ohne
# sie einzusetzen. Cap=5 ungenutzte cubes triggert die nachfolgenden Branches
# (create_field / market_list / propose_contract) — Pet wechselt zu Diversifikation.
MARKET_BUY_CUBE_CAP = 5


def _can_keep_buying_cubes(state: GameState) -> bool:
    """True wenn Pet noch unter dem Cube-Hoarding-Cap ist."""
    return _cube_count(state) < MARKET_BUY_CUBE_CAP


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
    """Cheapest preset the agent can afford; 'block' as default.

    Legacy v1.0.0-Behavior: always returns the most-expensive affordable preset
    (counter-intuitive; the for-loop walks ascending and overwrites). Kept for
    BASE_TREE-fallback compatibility. New code should use
    `_persona_preferred_preset(state, persona)` for evolve-aware selection.
    """
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


# v1.1.0 — Pattern-Tier-aware preset selection.
#
# Backend evolve-Mechanik (entity_tiers.py + decider_tree-Mirror REIFE_THRESHOLDS):
#   T1 → T2  needs entity_type=oscillator  (cost 1k)
#   T2 → T3  needs entity_type=spaceship   (cost 5k)
#   T3 → T4  needs entity_type=gun         (cost 25k)
#   T4 → T5  needs entity_type=breeder     (cost 125k)
#
# block (still_life) ist eine evolve-Sackgasse — der Pattern bleibt T1 für immer.
# blinker/toad sind T1-oscillator → können T1→T2 evolve.
# glider ist T1-spaceship → könnte T1→T2 evolve aber Backend will oscillator
# für T2, also wird Greedy auf glider gespart bis spätere Tier-Stufe.
#
# Persona-Map:
#   evolve-fokus (scientist, expansionist, farmer): blinker für oscillator-Pfad
#   non-evolve-fokus (warrior, trader, diplomat): block bleibt — billig,
#     für Markt/Kampf reicht still_life als territoriale Markierung.
PERSONA_PREFERRED_PRESETS: dict[str, str] = {
    "scientist": "blinker",
    "expansionist": "blinker",
    "farmer": "blinker",
    "warrior": "block",
    "trader": "block",
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
    """Pattern-Tier-aware preset selection (v1.1.0).

    Wählt das preset basierend auf persona-strategie + affordability.
    Fallback auf "block" wenn der bevorzugte preset nicht erschwinglich ist.
    """
    persona = (getattr(state, "persona_type", None) or "scientist").lower()
    preferred = PERSONA_PREFERRED_PRESETS.get(persona, "block")
    energy = _energy(state)
    if energy >= _PRESET_COST.get(preferred, 5):
        return preferred
    return "block"


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
    return ("place_cells", {"field_id": str(f.id), "preset": _persona_preferred_preset(state)})


def _act_place_cells_empty(state: GameState) -> tuple[str, dict[str, Any]]:
    """v1.1.0: persona-aware preset (was hardcoded `block`).

    scientist/expansionist/farmer get oscillator-pattern (`blinker`) so the
    field becomes T1-oscillator and qualifies for T1→T2 evolve once reife
    crosses 100. warrior/trader/diplomat keep `block` — they don't optimise
    for evolve and care about cost minimisation per fill.
    """
    f = _empty_field(state) or _fewest_cells_field(state)
    if f is None:
        return ("wait", {})
    return ("place_cells", {"field_id": str(f.id), "preset": _persona_preferred_preset(state)})


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
    # 6. Energy >= 100k AND cheap listing AND under cube-cap → market_buy
    (
        lambda s: (
            _energy(s) >= 100_000
            and _cheapest_buyable(s, 2_000) is not None
            and _can_keep_buying_cubes(s)
        ),
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
    """Persona-Branches haben Vorrang über empty-field-Survival-Refill (v1.1.0).

    Reihenfolge der Branches:
      1. CRITICAL_ENERGY < 100 → wait (absoluter Sink-Schutz)
      2. own_fields == 0 + can_afford → create_field (zero-state-bootstrap)
      3. Persona-spezifische Strategien (evolve / market_buy / create_field /
         market_list / propose_contract je nach Persona)
      4. empty_field → place_cells (Refill-Survival, fällt durch wenn (3) matched)
      5. fewest-cells → place_cells (Pflege-Fallback)
      6. wait

    v1.0.0 hatte (4) VOR (3) → reiche Agents (4.57 M E + viele Fields + ein
    leeres Feld) machten endlos place_cells statt market_list / propose_contract /
    create_field. Verifiziert S170 anhand comet-hand.

    Begründung der neuen Reihenfolge: bei rich-state ist Refill nicht
    rationaler als strategische Aktionen. Die Persona-Branches haben
    Energy-Schwellen (>=30 k bis >=100 k), die bei armen Agents nicht
    matchen — dort fällt der Tree natürlich auf empty_field zurück.
    """
    survival_critical = BASE_TREE[:2]  # critical-energy + 0-fields-create_field
    empty_fallback = [BASE_TREE[2]]  # empty_field → place_cells
    fallback = BASE_TREE[7:]  # fewest-cells + wait
    return survival_critical + persona_branches + empty_fallback + fallback


SCIENTIST_BRANCHES: list[Branch] = [
    # scientist: evolve > create_field > market_buy_blueprint > market_list_publish
    (lambda s: _has_evolvable_field(s), _act_evolve),
    (
        lambda s: (
            _energy(s) >= 100_000 and _cheapest_buyable(s, 2_000) and _can_keep_buying_cubes(s)
        ),
        _act_market_buy_under(2_000),
    ),
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
    (
        lambda s: (
            _energy(s) >= 100_000 and _cheapest_buyable(s, 2_000) and _can_keep_buying_cubes(s)
        ),
        _act_market_buy_under(2_000),
    ),
    (
        lambda s: _energy(s) >= 50_000 and _contract_target(s) is not None,
        _act_propose_non_aggression,
    ),
]

EXPANSIONIST_BRANCHES: list[Branch] = [
    # expansionist: create_field maximal > market_buy cheap_acquisition > place_cells bootstrap > evolve
    (lambda s: _energy(s) >= 5_000 and _has_universe_cube(s), _act_create_field),
    (
        lambda s: (
            _energy(s) >= 100_000 and _cheapest_buyable(s, 2_000) and _can_keep_buying_cubes(s)
        ),
        _act_market_buy_under(2_000),
    ),
    (lambda s: _any_field_below_cells(s, 30) is not None, _act_place_cells_fewest),
    (lambda s: _has_evolvable_field(s), _act_evolve),
    (
        lambda s: _energy(s) >= 50_000 and _contract_target(s) is not None,
        _act_propose_non_aggression,
    ),
]

TRADER_BRANCHES: list[Branch] = [
    # trader: market_buy primary > market_list monetise > evolve > create_field
    # Trader has cube-cap too (auch Markt-Experten können Cubes nicht endlos
    # horten ohne sie einzusetzen — sonst Liquiditäts-Problem ähnlich Bank-Run).
    (
        lambda s: (
            _energy(s) >= 100_000
            and _cheapest_buyable(s, _energy(s) * 0.1)
            and _can_keep_buying_cubes(s)
        ),
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
    (
        lambda s: _cheapest_buyable(s, 1_500) and _can_keep_buying_cubes(s),
        _act_market_buy_under(1_500),
    ),
    (lambda s: _market_list_offered(s, 30_000), _act_market_list(450)),
    (lambda s: _has_evolvable_field(s), _act_evolve),
    (lambda s: _energy(s) >= 5_000 and _has_universe_cube(s), _act_create_field),
]

FARMER_BRANCHES: list[Branch] = [
    # farmer: top-up (place_cells <50) > market_list surplus > evolve > market_buy cheap
    (lambda s: _any_field_below_cells(s, 50) is not None, _act_place_cells_fewest),
    (lambda s: _market_list_offered(s, 50_000), _act_market_list(450)),
    (lambda s: _has_evolvable_field(s), _act_evolve),
    (
        lambda s: _cheapest_buyable(s, 500) and _can_keep_buying_cubes(s),
        _act_market_buy_under(500),
    ),
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
    """Compass-Override: post-tree action-rewriting je nach Compass-Setting.

    MVP-Philosophie: leichte Anpassungen, kein voll-blockierender Override —
    der Tree bleibt die primäre Quelle, Compass tunet einzelne Resultate.

    Konzept §3.3 + v1.1.0-Erweiterung:

    +-------------+---------+--------------------------------------------------+
    | Compass     | Wirkung | Beispiel                                         |
    +-------------+---------+--------------------------------------------------+
    | consolidate | Pflege  | create_field → place_cells (eigene Felder zuerst)|
    | defend      | Schutz  | trade_agreement → non_aggression                 |
    | grow        | Expand. | place_cells → create_field bei rich-state + cube |
    | cooperate   | Verträge| place_cells → propose_contract bei target+energy |
    | attack      | Offens. | place_cells preset → glider (Spaceship-Pattern)  |
    | explore     | Markt   | create_field → market_buy bei cheap-blueprint    |
    +-------------+---------+--------------------------------------------------+

    Compass=None → no-op (Default für Pet, das kein Compass setzt).
    """
    if not compass:
        return action, params

    # consolidate: bevorzuge eigene Felder pflegen statt neuen anlegen
    if action == "create_field" and compass == "consolidate":
        f = _fewest_cells_field(state)
        if f is not None:
            return (
                "place_cells",
                {"field_id": str(f.id), "preset": _persona_preferred_preset(state)},
            )

    # defend: erzwinge non_aggression statt trade_agreement
    if action == "propose_contract" and compass == "defend":
        if params.get("contract_type") == "trade_agreement":
            new_params = dict(params)
            new_params["contract_type"] = "non_aggression"
            return action, new_params

    # v1.1.0 grow: bei place_cells umstellen auf create_field wenn rich + cube
    if action == "place_cells" and compass == "grow":
        if _energy(state) >= 50_000 and _has_universe_cube(state):
            cubes = list(getattr(state, "universe_cubes", []) or [])
            return ("create_field", {"cube_id": str(cubes[0].id)})

    # v1.1.0 cooperate: bei place_cells umstellen auf propose_contract wenn target+energy
    if action == "place_cells" and compass == "cooperate":
        target = _contract_target(state)
        if target is not None and _energy(state) >= 30_000:
            return (
                "propose_contract",
                {
                    "to_player_id": str(target.player_id),
                    "contract_type": "trade_agreement",
                    "terms": {"duration_ticks": 100},
                    "escrow_amount": 0,
                },
            )

    # v1.1.0 attack: place_cells-preset auf glider (T1-spaceship, offensiv)
    if action == "place_cells" and compass == "attack":
        new_params = dict(params)
        if _energy(state) >= _PRESET_COST.get("glider", 200):
            new_params["preset"] = "glider"
        return action, new_params

    # v1.1.0 explore: bei create_field umstellen auf market_buy wenn cheap-blueprint
    if action == "create_field" and compass == "explore":
        b = _cheapest_buyable(state, 2_000)
        if b is not None:
            return ("market_buy", {"listing_id": str(b.listing_id)})

    return action, params


# --- Decider-Klasse ---------------------------------------------------------


class TreeDecider:
    """Rule-based decision tree decider."""

    name: str = "tree"
    version: str = "1.1.1"

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
