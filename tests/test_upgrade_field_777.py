"""``upgrade_field`` (2.4.1, cosmergon#777): the tree builds up a field when the server offers it.

The server lists the offers in ``available_actions.upgrade_field`` (``available`` and ``offers``,
cheapest first). The tree takes the cheapest one when the balance still covers the subsistence
threshold after the price. Without the block, or with ``available: false``, it decides as before.
Against 2.4.0 the tests marked ``[red on 2.4.0]`` fail.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from cosmergon_pet.decider_tree import (
    VALID_ACTIONS,
    TreeDecider,
    _predict_delta,
    is_valid,
    resolve_action_params,
)
from cosmergon_pet.persona_profiles import (
    PERSONA_ACTION_BIAS,
    PERSONA_ACTION_POOLS,
    SUBSISTENCE_BIAS,
    SUBSISTENCE_POOL,
    subsistence_threshold,
)

# Scientist, one field with 150 cells (the "keep cells" goal of 100 is met), 10,000 energy:
# threshold = max(1,000 evolve, 575 field) * 2 = 2,000.
FIELD = SimpleNamespace(
    id="f1", entity_tier=1, entity_type="oscillator", reife_score=0, active_cell_count=150
)


def _state(
    upgrade: dict[str, Any] | None, *, energy: float = 10_000, persona: str = "scientist"
) -> Any:
    actions: dict[str, Any] = {"start_mission": {"available": False}}
    if upgrade is not None:
        actions["upgrade_field"] = upgrade
    return SimpleNamespace(
        persona_type=persona,
        energy=energy,
        fields=[FIELD],
        universe_cubes=[],
        available_actions=actions,
        world_briefing=SimpleNamespace(market=SimpleNamespace(buyable=[]), contract_targets=[]),
        compass_preset=None,
    )


def _offer(field_id: str, name: str, price: float, **extra: Any) -> dict[str, Any]:
    return {"field_id": field_id, "set": name, "price": price, **extra}


def _offers(*offers: dict[str, Any]) -> dict[str, Any]:
    return {"available": True, "offers": list(offers)}


def test_in_valid_actions_and_every_persona_pool_but_not_subsistence() -> None:
    """[red on 2.4.0]"""
    assert "upgrade_field" in VALID_ACTIONS
    for persona, pool in PERSONA_ACTION_POOLS.items():
        assert "upgrade_field" in pool, persona
        assert "upgrade_field" in PERSONA_ACTION_BIAS[persona], persona


def test_not_in_any_subsistence_pool() -> None:
    assert "upgrade_field" not in SUBSISTENCE_POOL
    assert "upgrade_field" not in SUBSISTENCE_BIAS


def test_bias_equals_the_evolve_bias_per_persona() -> None:
    for persona, bias in PERSONA_ACTION_BIAS.items():
        assert bias["upgrade_field"] == bias["evolve"], persona


def test_affordable_offer_is_valid_with_the_cheapest_offers_params() -> None:
    """[red on 2.4.0]: the cheapest offer wins, even when listed later; no ``at`` without one."""
    z = _state(
        _offers(
            _offer("f9", "walls", 900),
            _offer("f1", "segments", 400),
            _offer("f2", "towers", 700),
        )
    )
    assert is_valid(z, "upgrade_field") is True
    assert resolve_action_params(z, "upgrade_field", "scientist") == {
        "field_id": "f1",
        "set": "segments",
    }


def test_offer_with_at_passes_at_on() -> None:
    """[red on 2.4.0]"""
    z = _state(_offers(_offer("f1", "towers", 300, at="s:8:8"), _offer("f2", "walls", 500)))
    assert resolve_action_params(z, "upgrade_field", "scientist") == {
        "field_id": "f1",
        "set": "towers",
        "at": "s:8:8",
    }


def test_price_that_eats_the_subsistence_reserve_is_invalid() -> None:
    """[red on 2.4.0]: 2,400 is above the threshold, 2,400 - 500 is below it, 2,400 - 400 is on it."""
    threshold = subsistence_threshold("scientist", _state(None))
    assert threshold == 2_000
    z = _state(_offers(_offer("f1", "segments", 500)), energy=2_400)
    assert is_valid(z, "upgrade_field") is False
    assert resolve_action_params(z, "upgrade_field", "scientist") == {}
    assert _predict_delta(z, "upgrade_field", {}) == {}
    z = _state(_offers(_offer("f1", "segments", 400)), energy=2_400)
    assert is_valid(z, "upgrade_field") is True


@pytest.mark.parametrize(
    "block",
    [
        None,
        {"available": False},
        {"available": False, "offers": [_offer("f1", "segments", 100)]},
        {"available": True},
        {"available": True, "offers": []},
        {"available": True, "offers": "kaputt"},
        {"available": True, "offers": [{"field_id": "f1"}, "x", _offer("f1", "s", float("nan"))]},
        {"offers": [_offer("f1", "segments", 100)]},
    ],
)
def test_no_block_or_not_available_is_invalid(block: dict[str, Any] | None) -> None:
    z = _state(block)
    assert is_valid(z, "upgrade_field") is False
    assert resolve_action_params(z, "upgrade_field", "scientist") == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "block", [None, {"available": False, "offers": [_offer("f1", "segments", 100)]}]
)
async def test_without_block_or_when_not_available_the_decision_is_as_before(
    block: dict[str, Any] | None,
) -> None:
    """The reference is the same state without the key (what 2.4.0 saw)."""
    reference = await TreeDecider().decide(_state(None))
    assert await TreeDecider().decide(_state(block)) == reference
    assert reference[0] != "upgrade_field"


@pytest.mark.asyncio
async def test_tree_chooses_upgrade_field_where_it_chose_market_list_before() -> None:
    """[red on 2.4.0]: the scientist's cell goal is met (150 cells, goal 100), so ``place_cells``
    scores 0.1 + 0.0 and ``market_list`` 0.1 + 0.1 (a met goal scores 0.1 for every move); without
    an offer ``market_list`` wins. An offer gives ``upgrade_field`` 0.0 + 0.3 (the evolve bias)."""
    ohne = await TreeDecider().decide(_state(None))
    assert ohne[0] == "market_list"
    mit = await TreeDecider().decide(_state(_offers(_offer("f1", "segments", 400, at="s:2:3"))))
    assert mit == ("upgrade_field", {"field_id": "f1", "set": "segments", "at": "s:2:3"})


@pytest.mark.asyncio
async def test_blocked_upgrade_field_is_not_chosen() -> None:
    z = _state(_offers(_offer("f1", "segments", 400)))
    aktion, _ = await TreeDecider().decide(z, blocked=frozenset({"upgrade_field"}))
    assert aktion == "market_list"


@pytest.mark.asyncio
async def test_in_subsistence_the_move_is_not_taken() -> None:
    """Below the threshold the subsistence pool decides; ``upgrade_field`` is not in it."""
    z = _state(_offers(_offer("f1", "segments", 10)), energy=1_500)
    aktion, _ = await TreeDecider().decide(z)
    assert aktion != "upgrade_field"


@pytest.mark.asyncio
async def test_the_offer_as_read_in_production_is_taken() -> None:
    """[red on 2.4.1] The block Root-storm got from production on 20.11.2026, word for word,
    with its compass (attack), which favours ``place_cells``."""
    block = {
        "available": True,
        "offers": [
            {
                "field_id": "d6400d5b-0000-0000-0000-000000000000",
                "set": "fortify_core",
                "price": 6400.0,
                "at": "s:8:8",
            }
        ],
    }
    z = _state(block, energy=230_000)
    z.compass_preset = "attack"
    zug = await TreeDecider().decide(z)
    assert zug == (
        "upgrade_field",
        {"field_id": "d6400d5b-0000-0000-0000-000000000000", "set": "fortify_core", "at": "s:8:8"},
    )


@pytest.mark.parametrize("at", [7, True, "", 1.5, ["s:8:8"]])
def test_an_at_that_is_not_text_drops_the_offer(at: Any) -> None:
    assert not is_valid(_state(_offers(_offer("f1", "towers", 300, at=at))), "upgrade_field")
