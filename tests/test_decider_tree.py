"""Smoke tests for the vendored TreeDecider + tree_decision_loop integration.

Verifies:
  - TreeDecider produces an action from a minimal GameState
  - Personas pick different first-actions on the same state
  - tree_decision_loop calls agent.act when given a non-wait action
  - Mutual-exclusion check at run_pet level (llm_provider XOR tree_decider)
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from cosmergon_pet.decider_tree import VALID_ACTIONS, TreeDecider


def _make_state(
    *,
    persona: str = "scientist",
    energy: float = 10_000,
    fields: list[Any] | None = None,
    cubes: list[Any] | None = None,
    available_actions: dict[str, dict[str, Any]] | None = None,
) -> Any:
    """Lightweight GameState surrogate — duck-typed for the tree's getattr-paths."""
    return SimpleNamespace(
        persona_type=persona,
        energy=energy,
        fields=fields or [],
        universe_cubes=cubes or [],
        available_actions=available_actions or {},
        world_briefing=SimpleNamespace(
            market=SimpleNamespace(buyable=[]),
            contract_targets=[],
        ),
        compass_preset=None,
    )


@pytest.mark.asyncio
async def test_decider_returns_valid_action() -> None:
    state = _make_state()
    decider = TreeDecider()
    action, params = await decider.decide(state)
    assert action in VALID_ACTIONS
    assert isinstance(params, dict)


@pytest.mark.asyncio
async def test_decider_critical_energy_waits() -> None:
    state = _make_state(energy=10)  # below CRITICAL_ENERGY (100)
    decider = TreeDecider()
    action, _ = await decider.decide(state)
    assert action == "wait"


@pytest.mark.asyncio
async def test_decider_zero_fields_can_afford_creates_field() -> None:
    cube = SimpleNamespace(id="11111111-1111-1111-1111-111111111111")
    state = _make_state(
        energy=10_000,
        fields=[],
        cubes=[cube],
        available_actions={"create_field": {"can_afford": True}},
    )
    decider = TreeDecider()
    action, params = await decider.decide(state)
    assert action == "create_field"
    assert params["cube_id"] == str(cube.id)


@pytest.mark.asyncio
async def test_decider_unknown_persona_falls_back_to_scientist() -> None:
    state = _make_state(persona="some-future-persona", energy=10_000)
    decider = TreeDecider()
    action, _ = await decider.decide(state)
    assert action in VALID_ACTIONS  # scientist tree → always-valid action


@pytest.mark.asyncio
async def test_tree_loop_calls_agent_act_on_non_wait() -> None:
    """tree_decision_loop must execute the action when the tree picks one."""
    from cosmergon_pet.tree_loop import _one_tree_decision

    cube = SimpleNamespace(id="22222222-2222-2222-2222-222222222222")
    state = _make_state(
        energy=10_000,
        fields=[],
        cubes=[cube],
        available_actions={"create_field": {"can_afford": True}},
    )

    calls: list[tuple[str, dict[str, Any]]] = []

    class FakeAgent:
        state = None  # patched below

        async def act(self, action: str, **params: Any) -> Any:
            calls.append((action, params))
            return SimpleNamespace(success=True)

    agent = FakeAgent()
    agent.state = state  # type: ignore[assignment]

    captured: list[tuple[str, dict, float, bool]] = []

    def on_decision(action: str, params: dict, elapsed: float, success: bool) -> None:
        captured.append((action, params, elapsed, success))

    await _one_tree_decision(agent, TreeDecider(), on_decision)

    assert calls and calls[0][0] == "create_field"
    assert captured and captured[0][0] == "create_field"
    assert captured[0][3] is True


@pytest.mark.asyncio
async def test_tree_loop_skip_when_state_none() -> None:
    """If agent.state is None (not yet polled), the loop must not call act."""
    from cosmergon_pet.tree_loop import _one_tree_decision

    class FakeAgent:
        state = None

        async def act(self, action: str, **params: Any) -> Any:
            raise AssertionError("agent.act must not be called when state is None")

    captured: list[tuple[str, dict, float, bool]] = []
    await _one_tree_decision(FakeAgent(), TreeDecider(), lambda *a: captured.append(a))
    # Loop returned silently, no callback fired
    assert captured == []


def test_run_pet_rejects_both_backends() -> None:
    """Sanity: run_pet raises if both decider backends are passed."""
    from cosmergon_pet.face import run_pet

    async def _call() -> None:
        await run_pet(
            agent=None,  # type: ignore[arg-type]
            simulate=True,
            llm_provider=object(),
            tree_decider=object(),
        )

    with pytest.raises(ValueError, match="mutually exclusive"):
        asyncio.run(_call())


# ---------------------------------------------------------------------------
# v2.1.0 (S297) — Server-Wahrheit, Selbstbelohnungs-Fix, Backoff.
# Anlass: Comet-hand (feldlos, 9.953 Energie) wiederholte tagelang minuetlich
# dieselbe abgelehnte Aktion. Alle Tests hier sind rot gegen v2.0.2.
# ---------------------------------------------------------------------------


def _ml_actions(
    *, available: bool, energy: float = 0.0, items: dict | None = None
) -> dict[str, dict[str, Any]]:
    return {
        "market_list": {
            "available": available,
            "sellable_energy": energy,
            "sellable_items": items or {},
        }
    }


@pytest.mark.asyncio
async def test_market_list_respektiert_server_nein() -> None:
    """Server sagt available=false (kein Ueberschuss, kein Inventar) —
    der Baum darf market_list NICHT waehlen (v2.0.2 tat es: energy>=1500)."""
    from cosmergon_pet.decider_tree import is_valid

    state = _make_state(energy=9_953, available_actions=_ml_actions(available=False))
    assert is_valid(state, "market_list") is False
    action, _ = await TreeDecider().decide(state)
    assert action != "market_list"


def test_market_list_energie_bei_ueberschuss() -> None:
    """Server meldet verkaeufliche Energie → klassisches Energie-Listing."""
    from cosmergon_pet.decider_tree import _market_list_plan

    state = _make_state(
        energy=20_000,
        available_actions=_ml_actions(available=True, energy=2_500),
    )
    plan = _market_list_plan(state)
    assert plan == {"price_energy": 450}  # scientist


def test_market_list_item_mit_marktreferenz() -> None:
    """Kein Ueberschuss, aber gedecktes Inventar: 1 Item zu 95 % des
    billigsten aktiven Listings desselben Typs."""
    from cosmergon_pet.decider_tree import _market_list_plan

    state = _make_state(
        energy=9_953,
        available_actions=_ml_actions(available=True, items={"mega_bomb": 7}),
    )
    state.world_briefing.market.buyable = [
        SimpleNamespace(item_type="mega_bomb", price_energy=100_000.0),
        SimpleNamespace(item_type="mega_bomb", price_energy=120_000.0),
    ]
    plan = _market_list_plan(state)
    assert plan == {
        "item_type": "mega_bomb",
        "item_data": {"count": 1},
        "price_energy": 95_000,
    }


def test_market_list_item_ohne_referenzpreis_wird_nicht_gelistet() -> None:
    """Ohne Vergleichspreis am Markt wird nicht geraten — kein Listing."""
    from cosmergon_pet.decider_tree import _market_list_plan

    state = _make_state(
        energy=9_953,
        available_actions=_ml_actions(available=True, items={"bus_ticket_x": 1}),
    )
    assert _market_list_plan(state) is None


def test_market_list_alter_server_fallback() -> None:
    """Backend ohne sellable_*-Schluessel: altes Verhalten (Schwelle 1500)."""
    from cosmergon_pet.decider_tree import _market_list_plan

    state = _make_state(energy=9_953, available_actions={})
    assert _market_list_plan(state) == {"price_energy": 450}


def test_start_mission_ohne_selbstbelohnung_und_ohne_none_ids() -> None:
    """reward_energy muss 0 sein (S278-Tor) und params duerfen keine
    None-UUIDs tragen; feldlos + cubelos ⇒ kein Kandidat."""
    from cosmergon_pet.decider_tree import is_valid, resolve_action_params

    mit_feld = _make_state(fields=[SimpleNamespace(id="33333333-3333-3333-3333-333333333333")])
    params = resolve_action_params(mit_feld, "start_mission", "warrior")
    assert params["reward_energy"] == 0
    assert params["params"]["field_id"] == "33333333-3333-3333-3333-333333333333"

    feldlos = _make_state(fields=[], cubes=[])
    assert resolve_action_params(feldlos, "start_mission", "warrior") == {}
    assert is_valid(feldlos, "start_mission") is False


@pytest.mark.asyncio
async def test_decide_respektiert_blocked() -> None:
    """Eine gesperrte Aktion wird nicht gewaehlt — der Baum nimmt die
    naechstbeste statt zu haemmern."""
    field = SimpleNamespace(
        id="44444444-4444-4444-4444-444444444444",
        active_cell_count=5,
        entity_tier=1,
        reife_score=0,
        entity_type="still_life",
    )
    state = _make_state(energy=10_000, fields=[field])
    decider = TreeDecider()
    frei, _ = await decider.decide(state)
    geblockt, _ = await decider.decide(state, blocked=frozenset({frei}))
    assert geblockt != frei


def test_backoff_sperrt_nach_drei_fehlschlaegen_und_laeuft_ab() -> None:
    from cosmergon_pet.tree_loop import BACKOFF_ROUNDS, _Backoff

    b = _Backoff()
    for _ in range(3):
        b.naechste_runde()
        b.melde("market_list", success=False)
    assert "market_list" in b.blocked()
    # Erfolg einer ANDEREN Aktion aendert nichts an der Sperre
    b.melde("place_cells", success=True)
    assert "market_list" in b.blocked()
    # Sperre laeuft nach BACKOFF_ROUNDS Runden ab
    for _ in range(BACKOFF_ROUNDS):
        b.naechste_runde()
    assert "market_list" not in b.blocked()
    # Erfolg der Aktion selbst setzt den Zaehler zurueck
    b.melde("market_list", success=False)
    b.melde("market_list", success=True)
    b.melde("market_list", success=False)
    b.melde("market_list", success=False)
    assert "market_list" not in b.blocked()


def test_market_list_item_mit_server_referenzpreis() -> None:
    """Backend >= v1.64.31 liefert reference_prices — die gewinnen gegen das
    Briefing (das nur die 20 billigsten Listings traegt und mega_bomb nie)."""
    from cosmergon_pet.decider_tree import _market_list_plan

    actions = _ml_actions(available=True, items={"mega_bomb": 7})
    actions["market_list"]["reference_prices"] = {"mega_bomb": 100_000.0}
    state = _make_state(energy=9_953, available_actions=actions)
    # Briefing bewusst leer — der Serverpreis muss reichen.
    plan = _market_list_plan(state)
    assert plan == {
        "item_type": "mega_bomb",
        "item_data": {"count": 1},
        "price_energy": 95_000,
    }


def test_propose_contract_nur_backend_typen_mit_pflicht_terms() -> None:
    """Jede Persona sendet einen Vertragstyp, den das Backend kennt, mit
    vollstaendigen Pflicht-Terms.

    S298: der Baum erfand "research_agreement" (existiert im Backend nicht,
    validate_terms -> "Unknown contract type" -> HTTP 400) und sandte
    trade_agreement ohne den Pflicht-Term fee_discount_pct (dieselbe 400).
    Referenz abgeschrieben aus dem Backend (models/contract.py:CONTRACT_TYPES,
    Free-Tier-Teilmenge agent_game.py:_FREE_CONTRACT_TYPES) — der Pet ist ein
    free-Agent und darf nur diese Typen proponieren.
    """
    from cosmergon_pet.decider_tree import resolve_action_params

    free_types_required_terms = {
        "non_aggression": {"duration"},
        "trade_agreement": {"fee_discount_pct", "duration"},
    }
    target = SimpleNamespace(player_id="55555555-5555-5555-5555-555555555555")
    personas = [
        "scientist",
        "trader",
        "warrior",
        "diplomat",
        "farmer",
        "expansionist",
        "some-future-persona",
    ]
    for persona in personas:
        state = _make_state(persona=persona)
        state.world_briefing.contract_targets = [target]
        params = resolve_action_params(state, "propose_contract", persona)
        ctype = params["contract_type"]
        assert ctype in free_types_required_terms, (
            f"{persona}: '{ctype}' ist kein free-tier-proponierbarer Backend-Typ"
        )
        missing = free_types_required_terms[ctype] - set(params["terms"])
        assert not missing, f"{persona}/{ctype}: fehlende Pflicht-Terms {missing}"
        assert params["to_player_id"] == "55555555-5555-5555-5555-555555555555"
