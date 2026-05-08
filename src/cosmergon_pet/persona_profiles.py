"""Persona profiles for TreeDecider v2.0.2 (GOBT — Goal-Oriented Behavior Tree).

VENDORED from ``cosmergon-decider-tree`` v2.0.2
(``research/decider-cluster/decider-tree/src/cosmergon_decider_tree/persona_profiles.py``).

Two layers:
1. **Subsistenz** (universal): when energy < threshold → energy-earning actions.
2. **Persona-Kern-Charakter** (individual): 6 personas with their own life
   cycle, action pool, goal metric, bias.

Persona-Bias additive [-0.3, +0.3]. Goal-Score in [0, 1]. Final =
base_score + persona_bias + compass_bias. Goal logic dominant, persona
shapes as tiebreaker.

Source: docs/konzepte/konzept-decider-tree-v2.md (private cosmergon repo).
"""

from __future__ import annotations

from typing import Any

# --- Subsistenz-Layer --------------------------------------------------------

SUBSISTENCE_POOL: tuple[str, ...] = ("place_cells", "market_list", "create_field")
"""Aktionen die Energy bringen können (universal, persona-unabhängig)."""

SUBSISTENCE_BIAS: dict[str, float] = {
    "place_cells": 0.0,
    "market_list": 0.0,
    "create_field": 0.0,
}
"""Im Subsistenz-Modus alle gleichberechtigt — Goal-Score entscheidet."""


# Conway-Mechanik-Konstanten (für Subsistenz-Threshold-Berechnung)
EVOLUTION_COST_BY_TIER: dict[int, int] = {1: 1_000, 2: 5_000, 3: 25_000, 4: 125_000}
"""Kosten für evolve von Tier N → N+1 (aus backend/app/core/entity_tiers.py)."""

FIELD_COST_BASE: int = 500
"""Backend-Default für Field-Cost-Wachstum (next_cost = FIELD_COST_BASE * len(fields))."""


def subsistence_threshold(persona: str, state: Any) -> float:
    """Energy-Schwelle für Subsistenz-Modus pro Persona.

    Threshold = max(persona_kern_aktion_kosten) * 2. Pet braucht
    mindestens das 2× der teuersten Charakter-Aktion damit es seine
    Persona-Charakter-Aktionen ausführen kann + Reserve für Maintenance/Decay.
    """
    fields = list(getattr(state, "fields", []) or [])
    next_field_cost = FIELD_COST_BASE * len(fields) * 1.15  # mit Safety-Margin

    # Höchstes evolve-Tier in Reichweite (Tier+1 das Pet erreichen könnte)
    max_tier = max((getattr(f, "entity_tier", 1) or 1 for f in fields), default=1)
    evolve_max = EVOLUTION_COST_BY_TIER.get(max_tier, 125_000)

    # Persona-spezifische Kern-Aktion-Kosten
    costs_by_persona: dict[str, list[float]] = {
        "scientist": [evolve_max, next_field_cost],
        "trader": [10_000, next_field_cost],  # market_list_min als Trader-Kerngeschäft
        "warrior": [5_000, next_field_cost],  # place_cells multi-field + escrow
        "expansionist": [next_field_cost],  # create_field ist Kerngeschäft
        "diplomat": [10_000, 1_500],  # contract_escrow + market_buy goodwill
        "farmer": [evolve_max, 5_000],  # evolve + multi-field place_cells
    }
    return max(costs_by_persona.get(persona, costs_by_persona["scientist"])) * 2


def needs_subsistence(state: Any, persona: str) -> bool:
    """True wenn Energy unter Subsistenz-Threshold (Pet kann Charakter nicht ausleben)."""
    energy = float(getattr(state, "energy", 0) or 0)
    return energy < subsistence_threshold(persona, state)


# --- Persona-Kern-Charakter --------------------------------------------------

PERSONA_ACTION_POOLS: dict[str, tuple[str, ...]] = {
    "scientist": (
        # Forscher: Experimente, evolve, Publikation, Acquire, Forschungs-Kollab
        "place_cells",  # Experiment-Pattern (preset=blinker/toad/glider)
        "evolve",  # Tier-Aufstieg
        "market_list",  # Forschungs-Output veröffentlichen
        "market_buy",  # fremde Patterns acquirieren (cube/field-only)
        "propose_contract",  # research_agreement
        # create_field bleibt erlaubt aber niedrig-priorisiert — Subsistenz-Pfad
        "create_field",
    ),
    "trader": (
        # Trader: Markt-zentriert, Buy/Sell-Spread, Inventar verwenden
        "market_buy",  # Buy-Side Kerngeschäft (alle item_types)
        "market_list",  # Sell-Side Kerngeschäft
        "propose_contract",  # trade_agreement
        "create_field",  # Inventar-Use (Cubes verbauen)
        "place_cells",  # Inventar-Use (Presets verbauen)
        # evolve niedrig-priorisiert
        "evolve",
    ),
    "warrior": (
        # Krieger: Territorium, Defense, Diplomatie als Defensiv-Strategie
        "place_cells",  # Territorial-Markierung (preset=block) + Front-Refill
        "propose_contract",  # non_aggression als Defensiv-Pakt
        "evolve",  # Kraftaufbau
        "create_field",  # neues Territorium
        "market_buy",  # nur cube/field
        # market_list niedrig — Krieger ist nicht Trader
        "market_list",
    ),
    "expansionist": (
        # Eroberer: maximale Field-Expansion mit minimaler Pflege
        "create_field",  # Kerngeschäft
        "place_cells",  # minimal Fill (preset=block)
        "market_buy",  # cube/field acquirieren
        # evolve, market_list, propose_contract niedrig
        "evolve",
        "market_list",
        "propose_contract",
    ),
    "diplomat": (
        # Vermittler: Verträge primär, Goodwill via Markt
        "propose_contract",  # Kerngeschäft
        "market_buy",  # Goodwill via cheap-Listings
        "place_cells",  # minimal
        "market_list",  # Surplus moderat
        "create_field",  # nur bei Bedarf
        # evolve niedrig
        "evolve",
    ),
    "farmer": (
        # Landwirt: Felder pflegen, evolve, Surplus listen
        "place_cells",  # Kerngeschäft (cells halten)
        "evolve",  # Tier-Effizienz
        "market_list",  # Surplus monetisieren
        "market_buy",  # nur sehr cheap (Schnäppchen)
        "create_field",  # gelegentliche Erweiterung
        # propose_contract niedrig
        "propose_contract",
    ),
}


PERSONA_ACTION_BIAS: dict[str, dict[str, float]] = {
    "scientist": {
        "evolve": +0.3,  # Forscher-Kerngeschäft
        "market_list": +0.1,  # Publish ist gut
        "place_cells": +0.0,  # neutral (Experiment ODER Pflege)
        "market_buy": +0.0,  # Acquire ist neutral
        "propose_contract": -0.1,  # gelegentlich, nicht reflexartig
        "create_field": -0.2,  # nur bei Bedarf, nicht aggressiv
    },
    "trader": {
        "market_buy": +0.3,  # Buy-Side ist Kerngeschäft
        "market_list": +0.2,  # Sell-Side ist Kerngeschäft
        "propose_contract": +0.1,  # trade_agreement ist Trader-Strategie
        "create_field": +0.0,  # neutral (Inventar-Use)
        "place_cells": +0.0,  # neutral (Inventar-Use)
        "evolve": -0.3,  # nicht Trader-Kerngeschäft
    },
    "warrior": {
        "place_cells": +0.3,  # Territorium markieren + Front-Refill
        "propose_contract": +0.2,  # non_aggression ist Defensiv-Strategie
        "evolve": +0.0,  # neutral
        "create_field": +0.0,  # neutral
        "market_buy": -0.1,  # nur cube/field zum Bau
        "market_list": -0.2,  # Krieger handelt nicht
    },
    "expansionist": {
        "create_field": +0.3,  # Kerngeschäft
        "place_cells": +0.1,  # minimal Fill
        "market_buy": +0.0,  # cube acquire
        "evolve": -0.2,
        "market_list": -0.2,
        "propose_contract": -0.3,
    },
    "diplomat": {
        "propose_contract": +0.3,  # Kerngeschäft
        "market_buy": +0.1,  # Goodwill
        "place_cells": +0.0,
        "market_list": +0.0,
        "create_field": -0.1,
        "evolve": -0.3,
    },
    "farmer": {
        "place_cells": +0.3,  # Pflege ist Kerngeschäft
        "evolve": +0.2,  # Tier-Effizienz
        "market_list": +0.1,  # Surplus
        "market_buy": +0.0,  # Schnäppchen
        "create_field": +0.0,  # gelegentlich
        "propose_contract": -0.2,  # Bauer ist nicht Diplomat
    },
}


PERSONA_BUYABLE_TYPES: dict[str, tuple[str, ...] | None] = {
    "scientist": ("cube", "field"),
    "expansionist": ("cube", "field"),
    "farmer": ("cube", "field"),
    "warrior": ("cube", "field"),
    "diplomat": ("cube", "field", "preset"),  # Diplomat darf Presets als Goodwill kaufen
    "trader": None,  # alle item_types — Trader-Markt-Kerngeschäft
}
"""item_type-Filter im market_buy. v1.1.4-Filter (Anti-Hoarding) bleibt
in v2.0.0 erhalten. Trader = None (alle erlaubt). Diplomat darf preset
für Goodwill-Tausch."""


# --- Compass-Bias-Modifier ---------------------------------------------------

COMPASS_BIAS: dict[str, dict[str, float]] = {
    # Compass = temporärer Tweak des Persona-Bias. Wird additiv kombiniert.
    # Skala [-0.2, +0.2] — kleiner als Persona-Bias damit Persona dominant bleibt.
    "consolidate": {
        # Pflege bevorzugen, Wachstum drosseln
        "place_cells": +0.2,
        "evolve": +0.1,
        "create_field": -0.2,
        "market_buy": -0.1,
    },
    "defend": {
        # Defensiv-Verträge, Territorial-Refill
        "propose_contract": +0.2,
        "place_cells": +0.1,
        "create_field": -0.1,
    },
    "grow": {
        # Aggressive Expansion
        "create_field": +0.2,
        "market_buy": +0.1,
        "place_cells": -0.1,
    },
    "cooperate": {
        # Verträge bevorzugen
        "propose_contract": +0.2,
        "market_list": +0.1,
        "evolve": -0.1,
    },
    "attack": {
        # Aggressives Place-Cells (glider-Pattern), Krieger-Bias
        "place_cells": +0.2,
        "propose_contract": -0.1,
        "market_list": -0.1,
    },
    "explore": {
        # Markt-Aktivität bevorzugen
        "market_buy": +0.2,
        "market_list": +0.1,
        "create_field": -0.1,
    },
    "autonomous": {},  # kein Modifier (Default für Lab-Agents)
}


# --- Persona-Goal-Metric-Funktion --------------------------------------------


def persona_current_goal(state: Any, persona: str) -> dict[str, Any]:
    """Welches Goal-Metric ist im aktuellen State für die Persona aktiv?

    Goal-Metric beschreibt was die Persona als nächsten Schritt im
    Charakter-Zyklus erreichen will. Score-Funktion bewertet Aktionen
    danach wie sehr sie diese Distanz reduzieren.

    Returns dict mit "kind" und kind-spezifischen Parametern.
    """
    fields = list(getattr(state, "fields", []) or [])
    n_fields = len(fields)
    avg_cells = (
        sum(getattr(f, "active_cell_count", 0) or 0 for f in fields) / n_fields
        if n_fields > 0
        else 0
    )

    # Has any field with reife≥100 + matching entity_type for next-tier evolve?
    has_evolvable = any(
        (getattr(f, "reife_score", 0) or 0) >= 100
        and getattr(f, "entity_type", None) == "oscillator"
        and (getattr(f, "entity_tier", 0) or 0) == 1
        for f in fields
    )

    # Bootstrap (alle Personas): 0 Fields → erst ein Field bauen
    if n_fields == 0:
        return {"kind": "field_count_at_least", "target": 1}

    if persona == "scientist":
        # Forscher-Zyklus: 1) Experiment-Pattern aufbauen 2) reife wachsen lassen
        # 3) evolve 4) publish 5) acquire 6) collab
        if not any(getattr(f, "entity_type", None) in ("oscillator", "spaceship") for f in fields):
            return {"kind": "patterns_established", "target": 1}  # Experiment-Modus
        if has_evolvable:
            return {"kind": "evolved_fields_at_least", "target": 1}  # Evolve-Modus
        # Experiment-Pattern existiert + nicht evolve-fähig → Cells halten + Surplus monetisieren
        return {"kind": "avg_cells_at_least", "target": 100}

    elif persona == "trader":
        # Markt-Spread + Anti-Hoarding wenn cube/preset-Inventar groß
        cubes = list(getattr(state, "universe_cubes", []) or [])
        if len(cubes) >= 5:
            # Inventar-Use-Modus: Cubes verbauen
            return {"kind": "fields_use_inventory", "target": n_fields + 1}
        return {"kind": "energy_growth_via_market", "target": 1.1}  # 10 % Wachstum

    elif persona == "warrior":
        # Territorium + Defense + Pakte
        if any((getattr(f, "active_cell_count", 0) or 0) < 30 for f in fields):
            return {"kind": "all_fields_min_cells", "target": 30}
        return {"kind": "active_contracts_at_least", "target": 1}

    elif persona == "expansionist":
        # Maximale Field-Anzahl mit minimaler Pflege
        if any((getattr(f, "active_cell_count", 0) or 0) == 0 for f in fields):
            # Erst leeres Field minimal füllen, dann weiter expand
            return {"kind": "all_fields_min_cells", "target": 1}
        return {"kind": "field_count_at_least", "target": n_fields + 1}

    elif persona == "diplomat":
        # Vertrags-Netzwerk
        return {"kind": "active_contracts_at_least", "target": 3}

    elif persona == "farmer":
        # Felder pflegen + evolve
        if avg_cells < 50 and n_fields > 0:
            return {"kind": "avg_cells_at_least", "target": 50}
        if has_evolvable:
            return {"kind": "evolved_fields_at_least", "target": 1}
        return {"kind": "energy_at_least", "target": 100_000}  # Surplus aufbauen

    # Default scientist
    return {"kind": "avg_cells_at_least", "target": 100}


__all__ = [
    "COMPASS_BIAS",
    "EVOLUTION_COST_BY_TIER",
    "FIELD_COST_BASE",
    "PERSONA_ACTION_BIAS",
    "PERSONA_ACTION_POOLS",
    "PERSONA_BUYABLE_TYPES",
    "SUBSISTENCE_BIAS",
    "SUBSISTENCE_POOL",
    "needs_subsistence",
    "persona_current_goal",
    "subsistence_threshold",
]
