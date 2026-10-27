"""Waechter cos20 #587, zweite Runde: Vertragsbedingungen des LLM-Pfads, Whitelist-Pruefung
ohne Gegenstand, Pause des Autopiloten."""

from __future__ import annotations

import asyncio
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

from cosmergon_pet import face, llm_decider, tree_loop

REPO = Path(__file__).resolve().parents[1]

# Die Server-Regel, Stand 27.10.2026 (cos20 `models/contract.py` CONTRACT_TYPES,
# MAX_DURATION_TICKS, MAX_FEE_DISCOUNT_PCT; geprueft in `contract_manager.validate_terms`).
# Der Pet kann das Backend nicht importieren — die Kopie ist bewusst, aendert der Server die
# Regel, muss sie hier nachgezogen werden.
SERVER_PFLICHT = {
    "non_aggression": {"duration"},
    "trade_agreement": {"fee_discount_pct", "duration"},
}
SERVER_MAX_DURATION = 10_000
SERVER_MAX_FEE_DISCOUNT = 50.0


@pytest.mark.parametrize("vertragsart", sorted(SERVER_PFLICHT))
def test_llm_vertragsbedingungen_erfuellen_die_server_regel(vertragsart: str) -> None:
    """Der LLM-Pfad sendete {"duration_ticks": 100}: jeder Vorschlag „Missing required terms“."""
    terms = llm_decider._CONTRACT_TERM_TEMPLATES[vertragsart]
    assert SERVER_PFLICHT[vertragsart] <= set(terms)
    assert isinstance(terms["duration"], int) and 0 < terms["duration"] <= SERVER_MAX_DURATION
    if "fee_discount_pct" in terms:
        assert 0 < terms["fee_discount_pct"] <= SERVER_MAX_FEE_DISCOUNT


def _whitelist(pfad: Path) -> subprocess.CompletedProcess[str]:
    skript = REPO / "scripts" / "check-whitelist.sh"
    return subprocess.run(["bash", str(skript), str(pfad)], capture_output=True, text=True)


def test_whitelist_ohne_repo_ist_nicht_bestanden(tmp_path: Path) -> None:
    for pfad in (tmp_path / "gibt-es-nicht", tmp_path):
        lauf = _whitelist(pfad)
        assert lauf.returncode == 2, (pfad, lauf.stdout[-200:], lauf.stderr[-200:])
        assert "ALL CHECKS PASSED" not in lauf.stdout


@pytest.mark.skipif(shutil.which("git") is None, reason="braucht git (CI: ubuntu-latest)")
def test_whitelist_abschnitt_2_meldet_keinen_treffer_als_ok(tmp_path: Path) -> None:
    """Abschnitt 2 meldete OK bei genau einem Fehler (`ERRORS -lt 2`), auch beim eigenen."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "README.md").write_text("deployed on " + "Hetz" + "ner\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "README.md"], check=True)
    lauf = _whitelist(tmp_path)
    assert lauf.returncode == 1
    abschnitt_2 = lauf.stdout.split("--- 2.", 1)[1].split("--- 3.", 1)[0]
    assert "BLOCKER" in abschnitt_2 and "  OK" not in abschnitt_2


async def _nichts(*_a: Any, **_k: Any) -> None:
    return None


async def _kurz(*_a: Any, **_k: Any) -> float:
    return 0.01


class _Quelle:
    def __init__(self, **_k: Any) -> None: ...

    async def current(self, _agent: Any) -> object:
        return object()


def _schleifen_kurz(monkeypatch: pytest.MonkeyPatch, modul: Any) -> None:
    monkeypatch.setattr(modul, "StateSource", _Quelle)
    monkeypatch.setattr(modul, "aktueller_tick", _nichts)
    monkeypatch.setattr(modul, "sekunden_bis_zur_naechsten_runde", _kurz)
    monkeypatch.setattr(modul, "tick_wechsel_abwarten", _nichts)


class _Agent:
    def __init__(self, zuege: list[str]) -> None:
        self.zuege = zuege

    async def __aenter__(self) -> _Agent:
        return self

    async def __aexit__(self, *_a: Any) -> None:
        return None

    async def act(self, action: str, **_params: Any) -> None:
        self.zuege.append(action)


class _Baum:
    name = "attrappe"

    async def decide(self, _state: Any, blocked: frozenset = frozenset()) -> tuple[str, dict]:
        return "place_cells", {"preset": "block"}


class _Modell:
    name = "attrappe"
    model_string = "attrappe"


def _llm_zug_zaehlen(monkeypatch: pytest.MonkeyPatch, zuege: list[str]) -> None:
    async def entscheiden(*_a: Any, **_k: Any) -> None:
        zuege.append("llm")

    monkeypatch.setattr(llm_decider, "_one_decision", entscheiden)


async def _laufen_lassen(schleife: Any, sekunden: float) -> None:
    stop = asyncio.Event()
    asyncio.get_running_loop().call_later(sekunden, stop.set)
    await schleife(stop)


@pytest.mark.parametrize("pausiert", [True, False])
def test_baum_schleife_zieht_nicht_waehrend_der_pause(
    monkeypatch: pytest.MonkeyPatch, pausiert: bool
) -> None:
    _schleifen_kurz(monkeypatch, tree_loop)
    zuege: list[str] = []
    asyncio.run(
        _laufen_lassen(
            lambda stop: tree_loop.tree_decision_loop(
                _Agent(zuege), _Baum(), interval_s=0.01, stop=stop, paused=lambda: pausiert
            ),
            0.2,
        )
    )
    assert (zuege == []) is pausiert, zuege


@pytest.mark.parametrize("pausiert", [True, False])
def test_llm_schleife_zieht_nicht_waehrend_der_pause(
    monkeypatch: pytest.MonkeyPatch, pausiert: bool
) -> None:
    _schleifen_kurz(monkeypatch, llm_decider)
    zuege: list[str] = []
    _llm_zug_zaehlen(monkeypatch, zuege)
    asyncio.run(
        _laufen_lassen(
            lambda stop: llm_decider.llm_decision_loop(
                _Agent(zuege), _Modell(), interval_s=0.01, stop=stop, paused=lambda: pausiert
            ),
            0.2,
        )
    )
    assert (zuege == []) is pausiert, zuege


class _Geraet:
    def close(self) -> None: ...


def _pet_mit_zwei_langdruecken(monkeypatch: pytest.MonkeyPatch, spur: list) -> None:
    """run_pet ohne Hardware und Polls; der Encoder liefert sofort einen Langdruck, nach
    0,2 s den zweiten, nach 0,4 s endet der Pet (SIGINT). Jeder Langdruck landet in `spur`."""
    for name in (
        "_prime_state",
        "_poll_state",
        "_poll_events",
        "_poll_decisions",
        "_history_loop",
        "_draw_loop",
    ):
        monkeypatch.setattr(face, name, _nichts)

    def encoder(_simulate: bool, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop) -> _Geraet:
        queue.put_nowait(face.InputEvent.LONGPRESS)
        loop.call_later(0.2, queue.put_nowait, face.InputEvent.LONGPRESS)
        loop.call_later(0.4, os.kill, os.getpid(), signal.SIGINT)
        return _Geraet()

    monkeypatch.setattr(face, "make_display", lambda _simulate: _Geraet())
    monkeypatch.setattr(face, "make_encoder", encoder)
    original = face._handle_longpress

    async def langdruck(ps: face.PetState, agent: Any) -> None:
        await original(ps, agent)
        spur.append((time.monotonic(), "PAUSE"))

    monkeypatch.setattr(face, "_handle_longpress", langdruck)


@pytest.mark.parametrize("backend", ["baum", "llm"])
def test_langdruck_in_run_pet_haelt_den_autopiloten_an(
    monkeypatch: pytest.MonkeyPatch, backend: str
) -> None:
    """run_pet: zwischen Langdruck und zweitem Langdruck kein Zug (vorher: „PAUSED“ in der
    Anzeige, der Entscheider spielte weiter), nach dem zweiten zieht er wieder."""
    spur: list[tuple[float, str]] = []
    _pet_mit_zwei_langdruecken(monkeypatch, spur)

    class Spur(list):
        def append(self, zug: str) -> None:  # type: ignore[override]
            spur.append((time.monotonic(), zug))

    zuege = Spur()
    _schleifen_kurz(monkeypatch, tree_loop)
    _schleifen_kurz(monkeypatch, llm_decider)
    _llm_zug_zaehlen(monkeypatch, zuege)
    if backend == "baum":
        lauf = face.run_pet(
            _Agent(zuege), simulate=True, tree_decider=_Baum(), tree_interval_s=0.01
        )
    else:
        lauf = face.run_pet(
            _Agent(zuege), simulate=True, llm_provider=_Modell(), llm_interval_s=0.01
        )
    asyncio.run(lauf)
    pause, weiter = [t for t, was in spur if was == "PAUSE"]
    assert [was for t, was in spur if pause < t < weiter and was != "PAUSE"] == []
    assert [was for t, was in spur if t > weiter], spur
