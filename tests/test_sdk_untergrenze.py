"""The pet installs an SDK that cleans foreign text (cos20 #492, Betreuer-Durchgang ab1a021).

Everything the pet shows of other players and the server comes through cosmergon-agent, and the
SDK takes control characters and direction marks out of every answer since 0.31.1. Until 0.8.18
the package asked for 0.19.0, and the installer's ``pip install --upgrade git+...`` does not lift
a dependency that is already met: an old SDK stayed. ``install/requirements.txt``, the list of
runtime dependencies, named 0.7.0, and the test run installed 0.19.0. All three name one floor,
at least the version that cleans direction marks.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLEANS_DIRECTION_MARKS = (0, 31, 1)
FLOOR = re.compile(r"(?<![\w.-])cosmergon-agent>=([0-9]+)\.([0-9]+)\.([0-9]+)")
PLACES = ("pyproject.toml", "install/requirements.txt", ".github/workflows/pytest.yml")


def _floors(path: Path) -> list[tuple[int, int, int]]:
    found = FLOOR.findall(path.read_text(encoding="utf-8"))
    return [(int(a), int(b), int(c)) for a, b, c in found]


def test_package_list_and_test_run_name_one_floor_that_cleans_foreign_text() -> None:
    floors = {place: _floors(REPO / place) for place in PLACES}
    assert all(len(found) == 1 for found in floors.values()), floors
    assert len({found[0] for found in floors.values()}) == 1, f"one floor at all places: {floors}"
    assert floors["pyproject.toml"][0] >= CLEANS_DIRECTION_MARKS, floors


def test_the_floor_is_read_where_it_stands() -> None:
    """Control: the pattern reads the forms of the three files, not a name that only ends so."""
    assert FLOOR.findall('    "cosmergon-agent>=0.31.1",\n') == [("0", "31", "1")]
    assert FLOOR.findall("cosmergon-agent>=0.7.0\n") == [("0", "7", "0")]
    assert FLOOR.findall('pip install "cosmergon-agent>=0.31.1" "pillow"') == [("0", "31", "1")]
    assert FLOOR.findall("my-cosmergon-agent>=1.0.0\n") == []
    assert FLOOR.findall("cosmergon-agent-extra>=1.0.0\n") == []
