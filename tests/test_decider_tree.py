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
    compass: str | None = None,
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
        compass_preset=compass,
    )


def _fieldless_solvent_facts(**overrides: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Real server facts of a fieldless-but-solvent agent (v2.3.0 case):
    marauder in recovery, no bombs yet, richest loot field known,
    market_list available — and no free build slot."""
    facts: dict[str, dict[str, Any]] = {
        "start_mission": {
            "available": True,
            "marauder_state": "recovery",
            "mega_bombs": 0,
            "richest_loot_field": {
                "field_id": "a7cb9d65-b959-48bc-a2f6-76b073f57dc8",
                "bomb_boxes": 14,
            },
        },
        "market_list": {
            "available": True,
            "sellable_energy": 365.95,
            "sellable_items": {},
        },
        "create_field": {"can_afford": True, "next_cost": 500.0, "available": False},
    }
    facts.update(overrides)
    return facts


@pytest.mark.asyncio
async def test_solvent_fieldless_agent_takes_the_conquest_chain() -> None:
    """v2.3.0 regression (red vs v2.2.3): the 0.9 fieldless special-case was
    coupled to the subsistence goal (``energy_at_least``). A SOLVENT fieldless
    agent (goal ``field_count_at_least``) got 0.0 for start_mission and lost
    0.20:0.15 to market_list under the explore compass — listing every minute
    instead of returning to the game. Fieldless + server facts must win."""
    state = _make_state(
        energy=11_449,
        fields=[],
        cubes=[],  # full world: no build slot
        available_actions=_fieldless_solvent_facts(),
        compass="explore",
    )
    action, params = await TreeDecider().decide(state)
    assert action == "start_mission"
    assert params["params"]["mission_type"] == "gather_spores"


@pytest.mark.asyncio
async def test_free_slot_beats_conquest_despite_chain_facts() -> None:
    """Guard for the v2.2.1 ordering (0.9 < create_field): with a free and
    affordable build slot the fieldless special-case stays silent structurally
    — create_field wins even though the full conquest facts are present."""
    cube = SimpleNamespace(id="11111111-1111-1111-1111-111111111111")
    state = _make_state(
        energy=11_449,
        fields=[],
        cubes=[cube],  # free build slot
        available_actions=_fieldless_solvent_facts(),
        compass="explore",
    )
    action, params = await TreeDecider().decide(state)
    assert action == "create_field"
    assert params["cube_id"] == str(cube.id)


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
    inner = _draht(resolve_action_params(mit_feld, "start_mission", "warrior"))
    assert inner["reward_energy"] == 0
    assert inner["params"]["field_id"] == "33333333-3333-3333-3333-333333333333"

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


# Pet 0.4.3 (S299) — soziale Kadenz: ein ERFOLGREICHER Propose sperrt
# beide Propose-Aktionen. Anlass: 992 Proposes/24 h im Minutenraster, 800
# rejected, Reputation am Anschlag — die Ablehnung kommt asynchron nach
# success=True, der Fehlschlag-Backoff sieht sie nie.


def test_sozial_kadenz_erfolgreicher_propose_sperrt_beide_propose_aktionen() -> None:
    """Rot gegen Alt-Code: dort loeschte ein Erfolg die Sperre nur."""
    from cosmergon_pet.tree_loop import SOZIAL_KADENZ_ROUNDS, _Backoff

    b = _Backoff()
    b.naechste_runde()
    b.melde("propose_contract", success=True)
    # BEIDE Zwillinge gesperrt — sonst weicht der Baum auf den Template-Weg aus.
    assert "propose_contract" in b.blocked()
    assert "propose_from_template" in b.blocked()
    # Kadenz laeuft ab, danach ist der naechste Antrag wieder erlaubt.
    for _ in range(SOZIAL_KADENZ_ROUNDS):
        b.naechste_runde()
    assert "propose_contract" not in b.blocked()
    assert "propose_from_template" not in b.blocked()


def test_sozial_kadenz_nicht_soziale_erfolge_sperren_nichts() -> None:
    """Ueberkorrektur-Waechter: market_list/place_cells bleiben kadenzfrei."""
    from cosmergon_pet.tree_loop import _Backoff

    b = _Backoff()
    b.naechste_runde()
    b.melde("market_list", success=True)
    b.melde("place_cells", success=True)
    assert b.blocked() == frozenset()


def test_sozial_kadenz_ueberschreibt_keinen_laengeren_fehlschlag_backoff() -> None:
    """max()-Semantik: eine bestehende laengere Sperre wird nicht verkuerzt."""
    from cosmergon_pet.tree_loop import (
        BACKOFF_ROUNDS,
        SOZIAL_KADENZ_ROUNDS,
        _Backoff,
    )

    b = _Backoff()
    # propose_from_template steht nach 3 Fehlschlaegen im Fehlschlag-Backoff …
    for _ in range(3):
        b.naechste_runde()
        b.melde("propose_from_template", success=False)
    assert "propose_from_template" in b.blocked()
    # … ein ERFOLG des Zwillings setzt die Kadenz, verkuerzt die Sperre aber
    # nicht unter ihr bestehendes Ende (beide Enden liegen hier gleichauf:
    # Runde 3 + 30 — der Test dokumentiert die max()-Regel fuer den Fall,
    # dass die Konstanten je auseinanderlaufen).
    b.melde("propose_contract", success=True)
    ende = max(BACKOFF_ROUNDS, SOZIAL_KADENZ_ROUNDS)
    for _ in range(ende - 1):
        b.naechste_runde()
    assert "propose_from_template" in b.blocked()
    b.naechste_runde()
    assert "propose_from_template" not in b.blocked()


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


def test_propose_from_template_params_genestet_und_free_tier() -> None:
    """template_id/mode/slots muessen im params-Sub-Dict reisen (das SDK legt
    act()-kwargs flach in den Body, ActionRequest kennt sie nicht -> 422),
    und nur Free-Tier-Templates T07/T08 (T09/T06 rendern zu alliance/tribute,
    die 402-Klasse des direkten propose_contract-Wegs). S298 am Live-Fall
    Comet-hand: 3x 422 direkt nach dem v2.1.1-Deploy."""
    from cosmergon_pet.decider_tree import resolve_action_params

    required_slots = {
        "T08_NON_AGGRESSION": {"partner_id", "duration"},
        "T07_TRADE_AGREEMENT": {"partner_id", "fee_discount_pct", "duration"},
    }
    target = SimpleNamespace(player_id="66666666-6666-6666-6666-666666666666")
    for persona in ["scientist", "trader", "warrior", "diplomat", "farmer", "expansionist"]:
        state = _make_state(persona=persona)
        state.world_briefing.contract_targets = [target]
        out = resolve_action_params(state, "propose_from_template", persona)
        assert set(out) == {"params", "escrow_amount"}, f"{persona}: {set(out)}"
        inner = out["params"]
        tid = inner["template_id"]
        assert tid in required_slots, f"{persona}: {tid} ist kein Free-Tier-Template"
        missing = required_slots[tid] - set(inner["slots"])
        assert not missing, f"{persona}/{tid}: fehlende Slots {missing}"
        assert inner["mode"] == "targeted"


# ---------------------------------------------------------------------------
# S306 — Der feldlose Agent muss zurückfinden
# ---------------------------------------------------------------------------


def _cube(name: str = "c1") -> Any:
    return SimpleNamespace(id=f"cube-{name}", name=name)


def _feldloser_zustand(*, persona: str, erreichbar: list[Any], bauplaetze: list[Any]) -> Any:
    """Socket-hands Lage am 22.08.2026: kein Feld, Welt voll, Cubes erreichbar."""
    st = _make_state(persona=persona, fields=[], cubes=bauplaetze)
    st.reachable_cubes = erreichbar
    return st


def _draht(params: dict) -> dict:
    """Die Draht-Form: act(**ergebnis) muss ActionRequest.params fuellen.

    v2.2.2-Gegenprobe: die Tests hier pruefen seither den DRAHT-Vertrag
    (params.mission_type), nicht die Client-Innenform — die flache Form
    lief seit S306 still in 422, weil Pydantic Unbekanntes verwirft und
    genau diese Tests die falsche Form gruen hielten."""
    assert set(params.keys()) == {"params"}, f"nicht draht-konform: {sorted(params)}"
    inner = params["params"]
    assert inner.get("reward_energy") == 0
    return inner


def test_terminal_wird_ueber_erreichbare_cubes_gewaehlt() -> None:
    """Der heutige Ausfall: `universe_cubes` ist in voller Welt leer.

    Vorher las die Terminal-Wahl genau diese Liste — und fiel deshalb auf
    `gather_spores` zurück, das ein eigenes Feld braucht. Ergebnis: `{}`, keine
    Mission, der Agent blieb stehen.
    """
    from cosmergon_pet.decider_tree import resolve_action_params

    st = _feldloser_zustand(persona="scientist", erreichbar=[_cube()], bauplaetze=[])
    params = resolve_action_params(st, "start_mission", "scientist")
    assert params, "keine Mission trotz erreichbarem Cube"
    inner = _draht(params)
    assert inner["mission_type"] == "scout_terminal"
    assert inner["params"]["cube_id"] == "cube-c1"


def test_feldloser_klaert_auf_egal_welche_persona() -> None:
    """Besitz ist Existenzgrundlage, keine Stilfrage.

    `diplomat` bekäme sonst `patrol_field`, `warrior` `gather_spores` — beide
    brauchen ein eigenes Feld und liefern `{}`.
    """
    from cosmergon_pet.decider_tree import resolve_action_params

    for persona in ("diplomat", "warrior", "trader", "farmer", "expansionist"):
        st = _feldloser_zustand(persona=persona, erreichbar=[_cube()], bauplaetze=[])
        params = resolve_action_params(st, "start_mission", persona)
        typ = _draht(params)["mission_type"]
        assert typ == "scout_terminal", f"{persona}: {typ} statt Aufklärung"


def test_agent_mit_feld_behaelt_seine_persona_mission() -> None:
    """Der Notfallweg darf den Normalbetrieb nicht überschreiben."""
    from cosmergon_pet.decider_tree import resolve_action_params

    feld = SimpleNamespace(id="f1", active_cell_count=100, hole_count=0, entity_tier=1)
    st = _make_state(persona="diplomat", fields=[feld], cubes=[])
    st.reachable_cubes = [_cube()]
    params = resolve_action_params(st, "start_mission", "diplomat")
    assert _draht(params)["mission_type"] != "scout_terminal"


def test_ohne_erreichbaren_cube_keine_terminal_mission() -> None:
    """Kein Ziel → kein Versuch. Ein leeres params-Objekt wäre ein 422."""
    from cosmergon_pet.decider_tree import resolve_action_params

    st = _feldloser_zustand(persona="scientist", erreichbar=[], bauplaetze=[])
    assert resolve_action_params(st, "start_mission", "scientist") == {}


def test_alter_server_ohne_reachable_cubes_faellt_zurueck() -> None:
    """Backend < S306 kennt das Feld nicht — dann gilt die alte Liste."""
    from cosmergon_pet.decider_tree import _reachable_cubes

    st = _make_state(cubes=[_cube("alt")])
    assert not hasattr(st, "reachable_cubes")
    assert [c.id for c in _reachable_cubes(st)] == ["cube-alt"]


# ---------------------------------------------------------------------------
# S307 — Eroberungs-Kette: der Server nennt die Fakten, der Client geht den Weg
# ---------------------------------------------------------------------------


def _landweg_zustand(*, bomben: int, ziele: list, loot_id: str | None) -> Any:
    """Socket-hands Lage am 23.08. NACH v1.64.143: der State trägt den Weg."""
    st = _feldloser_zustand(persona="diplomat", erreichbar=[_cube()], bauplaetze=[])
    sm: dict[str, Any] = {"mega_bombs": bomben}
    if loot_id:
        sm["richest_loot_field"] = {"field_id": loot_id, "bomb_boxes": 15}
    st.available_actions = {
        "start_mission": sm,
        "claim_field": {"targets": ziele, "claim_ticks": 100},
    }
    return st


def test_feldloser_ohne_bomben_lootet_das_reichste_feld() -> None:
    """gather_spores braucht KEIN eigenes Feld — nur ein existierendes Ziel.

    Vorher endete der Feldlose beim Terminal (Intel ohne Anschluss): 27
    gather-Läufe von Socket-hand, alle vom 26.05., seither keiner."""
    from cosmergon_pet.decider_tree import resolve_action_params

    st = _landweg_zustand(bomben=0, ziele=[], loot_id="loot-94de")
    inner = _draht(resolve_action_params(st, "start_mission", "diplomat"))
    assert inner["mission_type"] == "gather_spores"
    assert inner["params"]["field_id"] == "loot-94de"


def test_feldloser_mit_bomben_belagert_das_erste_ziel() -> None:
    """Ab 3 Bomben wird belagert; die Folge-capture spawnt der Server."""
    from cosmergon_pet.decider_tree import resolve_action_params

    st = _landweg_zustand(
        bomben=3, ziele=[{"field_id": "ziel-052", "is_vulnerable": False}], loot_id="loot-94de"
    )
    inner = _draht(resolve_action_params(st, "start_mission", "diplomat"))
    assert inner["mission_type"] == "siege_field"
    assert inner["params"]["target_field_id"] == "ziel-052"


def test_bomben_ohne_ziel_looten_weiter() -> None:
    """3 Bomben, aber leere Zielliste: weiter sammeln statt ins Leere belagern."""
    from cosmergon_pet.decider_tree import resolve_action_params

    st = _landweg_zustand(bomben=5, ziele=[], loot_id="loot-94de")
    inner = _draht(resolve_action_params(st, "start_mission", "diplomat"))
    assert inner["mission_type"] == "gather_spores"


def test_ohne_landweg_fakten_bleibt_der_scout_fallback() -> None:
    """Server < v1.64.143 (keine Fakten im State): der S306-Notfallweg hält."""
    from cosmergon_pet.decider_tree import resolve_action_params

    st = _feldloser_zustand(persona="diplomat", erreichbar=[_cube()], bauplaetze=[])
    inner = _draht(resolve_action_params(st, "start_mission", "diplomat"))
    assert inner["mission_type"] == "scout_terminal"


def test_socket_hand_repro_subsistenz_gefaengnis_ist_offen() -> None:
    """Der echte Fall, END-TO-END durch decide(): Diplomat, 9.998 Energie
    (unter der 20k-Schwelle -> Subsistenz-Pool), 0 Felder, Welt voll.

    Vor v2.2.1 war market_list der einzige gueltige Zug des Pools — das
    wochenlange Karussell. Jetzt gewinnt die Eroberungs-Kette (0.9 > jeder
    market_list-Score), sobald der Server die Landweg-Fakten liefert."""
    import asyncio

    from cosmergon_pet.decider_tree import TreeDecider

    st = _landweg_zustand(bomben=0, ziele=[], loot_id="loot-94de")
    st.energy = 9_998.0
    st.my_mission = None
    st.pending_contracts = []

    action, params = asyncio.run(TreeDecider().decide(st))
    assert action == "start_mission"
    inner = _draht(params)
    assert inner["mission_type"] == "gather_spores"
    assert inner["params"]["field_id"] == "loot-94de"


def test_laufende_mission_sperrt_start_mission_serverseitig() -> None:
    """v2.2.3: der Server nennt marauder_state in den Fakten — nicht recovery
    heisst: Mission laeuft/Koerper unterwegs, jeder Start waere 422."""
    from cosmergon_pet.decider_tree import is_valid

    st = _landweg_zustand(bomben=0, ziele=[], loot_id="loot-94de")
    st.available_actions["start_mission"]["marauder_state"] = "mission"
    assert is_valid(st, "start_mission") is False

    st.available_actions["start_mission"]["marauder_state"] = "recovery"
    assert is_valid(st, "start_mission") is True


# --- v2.3.1 Kaufabsicht (S308, Live-Fall Socket-hand) ------------------------


def _preset_listing(price: float = 10.0) -> Any:
    return SimpleNamespace(listing_id="p1", item_type="preset", price_energy=price)


def _bomben_listing(price: float = 900.0) -> Any:
    return SimpleNamespace(listing_id="b1", item_type="mega_bomb", price_energy=price)


def test_voller_vorrat_kein_kauf_karussell_repro() -> None:
    """Der Socket-hand-Repro: diplomat, eigenes Feld, VOLLE Saat-Kammer,
    billiges Haus-Preset — gegen v2.3.0 war das ein garantierter Kauf
    (203 in 24 h). Mit Server-Faktum preset_stock >= 3 endet der Treadmill."""
    from cosmergon_pet.decider_tree import is_valid, resolve_action_params

    state = _make_state(
        persona="diplomat",
        fields=[SimpleNamespace(id="f1", entity_tier=1)],
        available_actions={"market_buy": {"preset_stock": 5}},
    )
    state.world_briefing.market.buyable = [_preset_listing()]
    assert is_valid(state, "market_buy") is False
    assert resolve_action_params(state, "market_buy", "diplomat") == {}


def test_leere_kammer_kauft_preset_nach() -> None:
    from cosmergon_pet.decider_tree import is_valid, resolve_action_params

    state = _make_state(
        persona="diplomat",
        fields=[SimpleNamespace(id="f1", entity_tier=1)],
        available_actions={"market_buy": {"preset_stock": 0}},
    )
    state.world_briefing.market.buyable = [_preset_listing()]
    assert is_valid(state, "market_buy") is True
    assert resolve_action_params(state, "market_buy", "diplomat")["listing_id"] == "p1"


def test_feldloser_mit_zielen_kauft_bomben() -> None:
    """Die Absicht ersetzt den statischen Typ-Filter: ein feldloser diplomat
    DARF die mega_bomb kaufen, wenn die Eroberungs-Kette sie braucht
    (Ziele sichtbar, Arsenal < 3) — der Kauf beschleunigt das Sammeln."""
    from cosmergon_pet.decider_tree import is_valid, resolve_action_params

    state = _make_state(
        persona="diplomat",
        energy=50_000,
        available_actions={
            "market_buy": {"preset_stock": 0},
            "start_mission": {"mega_bombs": 1},
            "claim_field": {"targets": [{"field_id": "z1"}]},
        },
    )
    state.world_briefing.market.buyable = [_bomben_listing()]
    assert is_valid(state, "market_buy") is True
    assert resolve_action_params(state, "market_buy", "diplomat")["listing_id"] == "b1"


def test_volles_arsenal_kauft_keine_bomben() -> None:
    from cosmergon_pet.decider_tree import is_valid

    state = _make_state(
        persona="diplomat",
        energy=50_000,
        available_actions={
            "market_buy": {"preset_stock": 0},
            "start_mission": {"mega_bombs": 3},
            "claim_field": {"targets": [{"field_id": "z1"}]},
        },
    )
    state.world_briefing.market.buyable = [_bomben_listing()]
    # Feldlos ohne eigenes Feld: preset-Absicht entfaellt (kein Feld),
    # Bomben-Absicht entfaellt (Arsenal voll) -> kein Kauf.
    assert is_valid(state, "market_buy") is False


def test_ohne_server_faktum_bleibt_legacy_verhalten() -> None:
    """Aelterer Server (kein market_buy.preset_stock): der Legacy-Typ-Filter
    traegt weiter — diplomat darf preset kaufen wie in v2.3.0 (durchlaessig,
    Muster marauder_state)."""
    from cosmergon_pet.decider_tree import is_valid

    state = _make_state(
        persona="diplomat",
        fields=[SimpleNamespace(id="f1", entity_tier=1)],
        available_actions={},
    )
    state.world_briefing.market.buyable = [_preset_listing()]
    assert is_valid(state, "market_buy") is True


def test_delta_folgt_demselben_kern() -> None:
    """Gate an einem von zwei Eingaengen ist keines: auch der Score-Delta
    sieht bei voller Kammer KEINEN Kauf (kein Geister-Delta fuer eine
    Aktion, die der Resolver verweigert)."""
    from cosmergon_pet.decider_tree import _predict_delta

    state = _make_state(
        persona="diplomat",
        fields=[SimpleNamespace(id="f1", entity_tier=1)],
        available_actions={"market_buy": {"preset_stock": 5}},
    )
    state.world_briefing.market.buyable = [_preset_listing()]
    assert _predict_delta(state, "market_buy", {}) == {}
