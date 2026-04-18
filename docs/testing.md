# Testing

Two layers run against every change before a human maker touches it:

| Layer | What it covers | Where it runs | Cost per run |
|---|---|---|---|
| **Runtime tests** (`tests/test_installer_runtime.py`) | Service template, lgpio FIFO-creation path, bug reproduction + fix regression | Any machine with `lgpio` importable | ~1 s |
| **Installer end-to-end** (`.github/workflows/test-installer.yml`) | Full `install.sh` run inside a real Raspberry Pi OS Lite aarch64 chroot, then the runtime tests | GitHub Actions, auto on push + PR that touch `install/`, `src/`, `pyproject.toml`, `tests/` or the workflow itself | ~3–4 min |

Both layers are needed. The runtime tests catch regressions in seconds but
cannot verify apt packages, pip-source-builds or aarch64 specifics. The CI
layer catches those but is too slow for the edit-try loop.

## Why this exists

Issue [#1](https://github.com/rkocosmergon/cosmergon-pet/issues/1) escaped
twice in a row:

- **v0.1.2** fixed the `swig`-missing build failure. It shipped without
  running the installer end-to-end, so the follow-up `-llgpio` linker
  failure was discovered by the maker, not the release.
- **v0.1.3** fixed the systemd runtime path. The service was inheriting
  `cwd=/` (system-mode default), where a non-root `User=` cannot write,
  so lgpio's notification FIFO (`.lgd-nfy*`) failed to be created and the
  Pet silently fell back to keyboard input.

After the second miss the verification gap became the release blocker.
These two test layers close it.

## What gets tested

### Layer 1 — runtime tests

`tests/test_installer_runtime.py` has three checks. They run standalone or
under pytest.

1. **Unit template static lint** — parses `install/install.sh` and asserts
   the generated systemd unit contains both `WorkingDirectory=${HOME}` and
   `Environment=HOME=${HOME}`. Fails loudly if someone removes them
   "because they look redundant."

2. **Bug reproduction** — runs a Python subprocess with `cwd=/` and a
   minimal env, calls `lgpio.notify_open()`, asserts the exact error
   signature that appeared on Lashee's Pi (`xCreatePipe` /
   `lgd-nfy` `FileNotFoundError`). If this check stops reproducing, either
   lgpio has changed semantics and we need to re-test the fix on current
   behaviour, or a dependency upgrade has silently reshuffled the path —
   either way, the reproduction is a canary.

3. **Fix regression** — runs the same probe with `cwd=$tmpdir`, asserts
   `notify_open()` returns a handle and the `.lgd-nfy*` files are created
   in that directory. If this check ever fails, the v0.1.3 fix has
   regressed and the runtime bug is back.

### Layer 2 — installer end-to-end

`.github/workflows/test-installer.yml` runs inside a chroot-based
virtualised Raspberry Pi OS Lite (aarch64) environment via
[`pguyot/arm-runner-action@v2`](https://github.com/pguyot/arm-runner-action).
The chroot has the exact apt repositories the maker's Pi has
(`deb.debian.org` + `archive.raspberrypi.com`), so `apt install swig
liblgpio-dev` resolves exactly like on hardware.

The workflow:

1. Creates a fresh non-root user `petrunner` (Pi OS Lite ships with `pi`
   locked via PAM nologin — `su - pi` would fail before any command
   runs; `sudo -u -H` ignores nologin).
2. Copies the repo into the user's home and runs
   `bash install/install.sh --no-systemd --no-i2c --dev`. This exercises:
   - `apt install python3-pip python3-venv python3-dev git swig liblgpio-dev`
     — verifies the package names resolve from the real rpi-archive.
   - `pip install git+https://…` into a fresh venv — verifies swig +
     liblgpio-dev are actually sufficient to build lgpio and rpi-lgpio
     from source on aarch64.
3. Runs the Layer-1 tests from inside the chroot. The bug reproduction
   is the meaningful assertion here: on a real aarch64 Pi OS Lite,
   without the fix, the FIFO cannot be created. This is what proves the
   issue is not a local simulation artifact.

### What is NOT tested

- **Real GPIO interaction.** The chroot does not expose
  `/dev/gpiochip0`, so `gpiochip_open()` and edge detection cannot be
  verified here. That boundary is only crossable on real Pi hardware.
  Makers report in Issue [#1](https://github.com/rkocosmergon/cosmergon-pet/issues/1)
  if the encoder fails to drive the face on their hardware.
- **The OLED display** (I²C device at 0x3C). Same reason.
- **`raspi-config nonint do_i2c 0`.** The chroot has no raspi-config.
  `--no-i2c` skips this; on hardware it runs.
- **systemd runtime behaviour.** The chroot has no running systemd, so
  `--no-systemd` installs everything except enabling the unit. The
  template is verified by Layer 1 instead.

## Running tests locally

### Prerequisites

`lgpio` has to be importable in the Python you invoke:

```bash
# Easiest path: run the Pet's installer in --dev mode
bash install/install.sh --no-systemd --no-i2c --dev
source ~/cosmergon-env/bin/activate
```

On a non-Raspberry Pi machine this still works — `lgpio`'s build is
pure userspace (`swig` + `liblgpio-dev`). On Debian / Ubuntu x86_64 you
need to build `liblgpio` from source
(https://github.com/joan2937/lg). The installer's apt path only works
on Raspberry Pi OS where liblgpio-dev is shipped via
archive.raspberrypi.com.

### Running

Standalone:

```bash
python3 tests/test_installer_runtime.py
```

Under pytest:

```bash
pip install pytest
pytest tests/test_installer_runtime.py -v
```

Both print one line per check. Exit code 0 on green, 1 on any failure.

### Expected output

```
PASS  unit template has WorkingDirectory + Environment=HOME
PASS  FIFO probe fails from cwd=/ (bug reproducible)
PASS  FIFO probe succeeds from cwd=$HOME (fix works)

All runtime tests passed.
```

## Running the CI layer locally

You don't — arm-runner-action is GitHub-runner-specific. For local
equivalents:

- **qemu-user-static + proot + a Pi OS Lite aarch64 rootfs** gives you
  a rootless chroot into real Pi OS Lite userspace. Useful for testing
  installer changes that need Pi OS apt repos. Walk-through:
  1. `apt-get download proot qemu-user qemu-user-static libtalloc2`
     (extract with `dpkg-deb -x`, no sudo).
  2. Download Pi OS Lite arm64 image, extract the rootfs partition
     with `debugfs` (no loop-mount needed, so no sudo).
  3. `proot -q qemu-aarch64-static -S rootfs bash` drops you into an
     aarch64 shell.
- **Docker + `--platform=linux/arm64`** on a host with qemu-user-static
  binfmt registered. One-liner setup via
  `docker run --privileged --rm tonistiigi/binfmt --install all`
  (needs sudo once).

Either gets you an arm64 userspace you can iterate in without pushing.
Keep the CI workflow as the authoritative gate — local reproductions
drift against whatever rpi-archive ships tomorrow.

## Writing new tests

### Adding to `tests/test_installer_runtime.py`

- Keep tests pytest-compatible (`def test_*`, assertions).
- Keep each test's intent in one short docstring.
- Prefer a subprocess over `os.chdir()` when you need a specific cwd.
  `os.chdir()` bleeds between tests and masks real service-start
  semantics.
- If you add a check that depends on a runtime artifact (a FIFO, a
  socket, a file), clean it up at the end — the CI chroot is shared
  between invocations of the workflow only across runs, but tests
  should not assume a tidy start-state.

### Adding a whole new file under `tests/`

The repo whitelist allows `tests/[A-Za-z0-9_/]+\.py` and
`tests/conftest.py`. `.sh` / other extensions need a whitelist update —
open an issue first (see `CONTRIBUTING.md`).

### Updating the workflow

Every change to `tests/`, `install/`, `src/` or `pyproject.toml`
triggers the CI workflow automatically. Changes to the workflow
itself also re-run it. There is no way to merge installer or source
changes that break the e2e flow without also editing the workflow
paths filter.

## Known failure modes (from building this suite)

- **`cp: cannot stat '/home/runner/work/…'`** — `$GITHUB_WORKSPACE`
  doesn't resolve inside the arm-runner chroot. Use cwd (`./`), which
  *is* the repo inside the chroot.
- **`This account is currently not available.`** — `su - pi` on Pi OS
  Lite hits PAM nologin because Pi OS ships the `pi` account locked.
  Create a fresh user and use `sudo -u -H` instead.
- **`rsync: command not found`** — Pi OS Lite Minimal has no rsync.
  `cp -a` works.
- **Test passes as root but fails as user** (or vice versa) — the
  bug reproduction check only has teeth if it runs as a non-root user.
  Root can write to `/`, so `cwd=/` never triggers the permission
  failure. Always run the runtime tests as a non-root user in CI.

## Further reading

- `install/install.sh` — the installer itself. Comments inline explain
  why `swig` + `liblgpio-dev` are both needed and why
  `WorkingDirectory` + `Environment=HOME` are both set.
- `CHANGELOG.md` — v0.1.0 through v0.1.3 document the layered
  discovery of issue [#1](https://github.com/rkocosmergon/cosmergon-pet/issues/1).
- `pguyot/arm-runner-action` README — the underlying CI primitive.
