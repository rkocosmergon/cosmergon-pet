"""End-to-end runtime test for the installer + systemd unit.

Runs in two contexts:
1. Locally (developer machine) — provided `lgpio` is importable, e.g. after
   running `pip install lgpio` or the full installer.
2. In CI via `pguyot/arm-runner-action@v2` inside a Raspberry Pi OS Lite
   aarch64 chroot, after `bash install/install.sh --no-systemd --no-i2c`.

Verifies:
- The systemd unit template in `install/install.sh` contains the runtime-
  environment directives that lgpio needs:
      WorkingDirectory=<writable dir>
      Environment=HOME=<same dir>
- `lgpio.notify_open()` succeeds from a writable cwd and fails from `/`
  with exactly the error signature Lashee saw on cosmergon-pet#1:
      xCreatePipe: Can't set permissions (436) for //.lgd-nfy0
      FileNotFoundError: [Errno 2] No such file or directory: '.lgd-nfy-3'

Run standalone: `python3 tests/test_installer_runtime.py`
Or via pytest:   `pytest tests/test_installer_runtime.py -v`
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INSTALLER = REPO / "install" / "install.sh"


def test_unit_template_has_workingdirectory_and_home() -> None:
    """Static lint: the service template must include WorkingDirectory and HOME."""
    text = INSTALLER.read_text()
    # Find the heredoc body (between the `[Service]` and `[Install]` section
    # headers of the generated unit file).
    service_start = text.index("[Service]")
    install_start = text.index("[Install]", service_start)
    block = text[service_start:install_start]

    assert "WorkingDirectory=${HOME}" in block, (
        "systemd unit is missing WorkingDirectory=${HOME}. "
        "Without it the service runs with cwd=/ and lgpio's notification FIFO "
        "(.lgd-nfy*) fails to be created — see cosmergon-pet#1."
    )
    assert "Environment=HOME=${HOME}" in block, (
        "systemd unit is missing Environment=HOME=${HOME}. "
        "liblgpio reads $HOME for its .lg_secret file; defensive belt-and-"
        "suspenders with WorkingDirectory — see cosmergon-pet#1."
    )


def _run_probe(cwd: str, home: str) -> tuple[int, str, str]:
    """Run a Python probe that triggers lgpio's FIFO-creation path.

    Returns (returncode, stdout, stderr). Runs in a fresh subprocess so the
    environment and cwd are exactly what systemd would hand a service.
    """
    probe = (
        "import lgpio, sys\n"
        "try:\n"
        "    h = lgpio.notify_open()\n"
        "    lgpio.notify_close(h)\n"
        "    print('OK')\n"
        "except Exception as e:\n"
        "    print('FAIL', type(e).__name__, e)\n"
        "    sys.exit(1)\n"
    )
    env = {"HOME": home, "PATH": "/usr/bin:/usr/local/bin"}
    # Preserve LD_LIBRARY_PATH / VIRTUAL_ENV so lgpio.so is findable in dev.
    for k in ("LD_LIBRARY_PATH", "VIRTUAL_ENV", "PYTHONPATH"):
        if k in os.environ:
            env[k] = os.environ[k]
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def test_fifo_probe_fails_from_root_cwd(tmp_path: Path) -> None:
    """With cwd=/ (system-mode systemd default) the FIFO creation must fail.

    This asserts that we can reproduce Lashee's symptom — any regression that
    silently "fixes" the reproduction (e.g. by making lgpio tolerate cwd=/)
    would mask the unit-test for the actual fix below.
    """
    try:
        import lgpio  # noqa: F401
    except ImportError:
        import pytest  # type: ignore[import-not-found]

        pytest.skip("lgpio not importable — run installer first")

    rc, stdout, stderr = _run_probe(cwd="/", home="/nonexistent")
    combined = stdout + stderr
    assert rc != 0, "Probe unexpectedly succeeded from cwd=/"
    assert "xCreatePipe" in combined or "lgd-nfy" in combined, (
        f"Expected the known lgpio FIFO-creation error; got:\n{combined}"
    )


def test_fifo_probe_succeeds_from_writable_cwd(tmp_path: Path) -> None:
    """With cwd=$HOME (the v0.1.3 fix) the FIFO creation must succeed."""
    try:
        import lgpio  # noqa: F401
    except ImportError:
        import pytest  # type: ignore[import-not-found]

        pytest.skip("lgpio not importable — run installer first")

    rc, stdout, _ = _run_probe(cwd=str(tmp_path), home=str(tmp_path))
    assert rc == 0, f"Probe failed from writable cwd — fix regressed:\n{stdout}"
    assert "OK" in stdout
    # FIFO should have been created and cleaned up; verify at least one
    # .lgd-nfy* was touched during the run.
    fifos = list(tmp_path.glob(".lgd-nfy*"))
    assert fifos, "No .lgd-nfy* files created — lgpio init path did not run"


# --- Standalone runner ------------------------------------------------------


def _main() -> int:
    import tempfile

    failures: list[str] = []

    try:
        test_unit_template_has_workingdirectory_and_home()
        print("PASS  unit template has WorkingDirectory + Environment=HOME")
    except AssertionError as e:
        print("FAIL  unit template:", e)
        failures.append("unit_template")

    try:
        import lgpio  # noqa: F401

        with tempfile.TemporaryDirectory() as td:
            tp = Path(td)
            try:
                test_fifo_probe_fails_from_root_cwd(tp)
                print("PASS  FIFO probe fails from cwd=/ (bug reproducible)")
            except AssertionError as e:
                print("FAIL  bug no longer reproduces:", e)
                failures.append("reproduce_bug")

            try:
                test_fifo_probe_succeeds_from_writable_cwd(tp)
                print("PASS  FIFO probe succeeds from cwd=$HOME (fix works)")
            except AssertionError as e:
                print("FAIL  fix broken:", e)
                failures.append("fix_works")
    except ImportError:
        print("SKIP  lgpio not importable (run installer first)")

    if failures:
        print(f"\n{len(failures)} failure(s): {failures}")
        return 1
    print("\nAll runtime tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
