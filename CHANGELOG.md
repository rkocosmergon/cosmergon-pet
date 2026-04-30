# Changelog

All notable changes to Cosmergon Pet are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.6] — 2026-04-30

### Added

- **Big-face screensaver.** After 30 s of no input on screen 1, the
  display switches to a centred ~24 px face (3× the default font size),
  filling the panel. The first encoder turn or click brings back the
  regular screen 1 immediately. Mood updates remain live in screensaver
  mode — `( -__- )` flips to `( ;__; )` if a catastrophe hits, etc.
  Long-press still pauses/resumes as everywhere else. Build feedback:
  the small-text default felt static on a desk; a big face turns the
  Pet into a desk companion at a glance.

### Implementation

- `OledDisplay.draw_big_face(face)` — uses `ImageFont.load_default(size=24)`
  (Pillow 10+) with `textbbox`-based centring, falls back to the default
  8 px font on older Pillow.
- `StdoutDisplay.draw_big_face(face)` — banner mode in the terminal
  for `--simulate` development.
- `_is_idle(ps, now)` — pure check: only screen 1, no menu open, idle
  beyond `SCREENSAVER_AFTER_SECONDS` (30 s).
- Tunables: `SCREENSAVER_AFTER_SECONDS`, `SCREENSAVER_FONT_SIZE`.

## [0.1.5] — 2026-04-30

### Fixed

- **OLED bottom-line clipping.** Some SH1106 1.3" I²C modules and the
  default PIL font on Pillow 11+ crop the last 1-2 px on the y-axis;
  the previous layout rendered 8 lines × 8 px = 64 px with no margin,
  so the bottom line of the face screen (and any 6-body-line screen)
  got partially clipped. The display layer now renders **7 lines with
  a 4 px top margin** (60 px total on a 64 px panel) and all screen
  renderers were normalised to **≤5 body lines** (header + separator +
  body = 7 lines). Reported as build feedback S156 — visible on the
  Face screen as the trailing world-event headline being half-cut.

### Changed

- **Build guide is now in English** and trimmed to three pages
  (~700 words, down from nine pages / ~1800 words). The 5-stage
  roadmap, the 8-screen catalogue and the duplicated wiring prose
  have been moved out of the printable guide. Body text is now
  left-aligned (no justify; rivers in tight columns hurt readability
  more than ragged-right does). The guide footer references v1.5.
- **Shop-link convention switched to globally available maker shops**
  (Pimoroni, The Pi Hut, Adafruit, AliExpress) in the README and BOM
  files. DACH-specific direct links (Amazon.de, Voelkner) remain as
  regional alternatives but are no longer the primary references.

### Added

- **`docs/onboarding.md`** — covers the two ways to attach a Cosmergon
  agent to a fresh Pet (auto-register vs. existing agent via
  activation code or `scp`). Linked from build-guide step 4.
- **`docs/troubleshooting.md`** — symptom-first FAQ. Opens with the
  four "quick fixes" that also appear as the mini-block at the end
  of the build guide, then catalogues specific failures from issue
  history (lgpio FIFO, swig build, GPIO group, async-with). Linked
  from the mini-block.

## [0.1.4] — 2026-04-18

### Fixed

- **Pet service** now opens the SDK HTTP client via `async with agent:`
  in `run_pet()`. Without it every `_request()` call raised
  `RuntimeError("Agent not connected. Call run() or use async with.")`
  from the SDK, which the Pet caught in `_poll_state` and surfaced on
  the display as `! state: Agent not co` on every info screen. The
  encoder and the display both worked; the Pet simply never reached
  the backend. Reported as part of
  [#1](https://github.com/rkocosmergon/cosmergon-pet/issues/1).

### Added

- **`tests/test_pet_startup.py`** — startup-level tests that catch this
  class of bug: a static lint on `run_pet()` requiring
  `async with agent:`, plus two canary tests that verify the SDK's
  `_client is None`-before-open invariant still holds and that the
  pre-flight RuntimeError fires on an unopened agent. Exercises the
  exact path `_prime_state()` hit on Lashee's Pi.
- **Build guide Schritt 4 — "Mit Cosmergon verbinden"** now documents
  both onboarding paths:
  - **A** (frischer Pet, kein Account): auto-register runs on first
    start, nothing to do.
  - **B** (bestehenden Agent umziehen): either copy the existing
    `AGENT-...:secret` key from another setup's
    `~/.cosmergon/config.toml` into `COSMERGON_API_KEY`, or redeem a
    fresh Stripe-checkout activation code with
    `cosmergon-agent activate COSM-XXXXXXXX`.
- **`src/cosmergon_pet/__main__.py`** — allows
  `python -m cosmergon_pet` alongside the `cosmergon-pet` entry
  point, which the new startup tests rely on.

### Process

- CI workflow (`test-installer.yml`) now runs both the installer
  runtime tests and the pet startup tests inside the Pi OS Lite
  aarch64 chroot, closing the verification gap that let this third
  layer of [#1](https://github.com/rkocosmergon/cosmergon-pet/issues/1)
  escape the v0.1.3 release.

## [0.1.3] — 2026-04-18

### Fixed

- **Systemd unit** now sets `WorkingDirectory=$HOME` and
  `Environment=HOME=$HOME`. Without them the service inherits the
  system-mode default cwd (`/`), which a non-root `User=` cannot write
  to. `lgpio` creates its notification FIFOs (`.lgd-nfy*`) via
  `getcwd()`, so the service would fail at runtime with:
  ```
  xCreatePipe: Can't set permissions (436) for //.lgd-nfy0,
    No such file or directory
  FileNotFoundError: [Errno 2] No such file or directory: '.lgd-nfy-3'
  ```
  and silently fall back to keyboard input — useless on a headless Pi.
  Reported as [#1](https://github.com/rkocosmergon/cosmergon-pet/issues/1).

### Added

- **`tests/test_installer_runtime.py`** — end-to-end runtime tests
  covering both failure modes from #1. The suite asserts the service
  template contains the runtime-environment directives and exercises
  lgpio's FIFO-creation path from both a writable cwd (must succeed)
  and `/` (must fail with the exact error signature). Pytest- and
  standalone-compatible.
- **`.github/workflows/test-installer.yml`** — CI workflow that runs
  the installer + runtime tests inside a chroot-based virtualised
  Raspberry Pi OS Lite (aarch64) environment via
  [`pguyot/arm-runner-action@v2`](https://github.com/pguyot/arm-runner-action).
  Every push and PR that touches `install/`, `src/`, `tests/` or
  `pyproject.toml` now runs the full install flow against a real Pi
  OS Lite image before anything reaches a maker. The gap that let
  bug #1 escape twice in a row is now closed.

## [0.1.2] — 2026-04-18

### Fixed

- **Installer** now apt-installs `swig` and `liblgpio-dev`. `rpi-lgpio`
  (added in 0.1.1) pulls `lgpio`, which has no prebuilt wheel for
  aarch64 Raspberry Pi and therefore builds its C extension from
  source. That build needs **two** things Raspberry Pi OS Lite does
  not ship by default:
  - `swig` (generates the Python wrapper), otherwise pip fails with
    `command 'swig' failed: No such file or directory`;
  - `liblgpio-dev` (headers + .so to link against `-llgpio`),
    otherwise the follow-up gcc step fails with
    `/usr/bin/ld: cannot find -llgpio`.
  `liblgpio-dev` ships from `archive.raspberrypi.com`, which is
  enabled by default on every Raspberry Pi OS install. Verified
  end-to-end by reproducing the swig-missing failure and the
  liblgpio-missing failure in sequence, then building `lgpio` and
  `rpi-lgpio` cleanly once both apt packages were in place.
  Follow-up to [#1](https://github.com/rkocosmergon/cosmergon-pet/issues/1).

## [0.1.1] — 2026-04-18

### Fixed

- **GPIO edge detection on Raspberry Pi OS Bookworm / kernel >=6.6.**
  Swapped dependency `RPi.GPIO` → `rpi-lgpio`, a drop-in namespace-
  compatible replacement built on `libgpiod`. The legacy `RPi.GPIO`
  library cannot register edge interrupts on modern kernels because
  the `/sys/class/gpio/*` sysfs interface has been removed; the Pet
  would silently fall back to keyboard input and the rotary encoder
  did nothing. No code change in `face.py` — same `import RPi.GPIO`
  call, different backend. Reported as
  [#1](https://github.com/rkocosmergon/cosmergon-pet/issues/1). The
  installer now also uninstalls any legacy `RPi.GPIO` it finds before
  reinstalling, so re-running it on an existing system just works.

### Fixed

- **Installer** (`install/install.sh`) now adds `$USER` to the `gpio`,
  `i2c` and `spi` groups if they're not already a member. Without
  membership in `gpio`, `GPIO.add_event_detect()` fails at runtime
  with *"Failed to add edge detection"* and the Pet silently falls
  back to keyboard input — which is useless when running headless via
  SSH. Reported as
  [#1](https://github.com/rkocosmergon/cosmergon-pet/issues/1).
- **Build guide v1.5:** Troubleshooting entry for the GPIO-group issue
  now uses `$USER` (not hardcoded `pi`), covers the exact error string
  users see and lists `spi` alongside `gpio` and `i2c`.
- **Build guide v1.6:** Step 1 (SD card) OS bullet now spells out the
  Imager path — "Raspberry Pi OS Lite (64-bit)" lives under
  *Choose OS → Raspberry Pi OS (other)*, not in the default list.
  Note that the Pet is built and tested against Lite, not the Desktop
  variant. Maker-reported hiccup on
  [#1](https://github.com/rkocosmergon/cosmergon-pet/issues/1).

### Added

- `hardware/wiring.svg` — schematic wiring diagram (Raspberry Pi
  header + OLED + KY-040 encoder, color-coded). Generated via
  `scripts/generate-wiring-svg.py`.
- `hardware/images/social-preview.png` (1280×640) — GitHub social
  preview. Generated via `scripts/generate-social-preview.py`.
- `SECURITY.md` — vulnerability reporting policy
- `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1
- `CONTRIBUTING.md` — PR guide and style
- `CHANGELOG.md` — this file
- `LICENSE`, `LICENSES/MIT.txt`, `LICENSES/CC-BY-SA-4.0.txt` — dual
  license (MIT for code, CC-BY-SA-4.0 for docs), REUSE-compliant
- `NOTICE` — trademark usage guidelines

### Removed

- All references to a non-existent M5Stack Dial port (README, hardware
  docs, build guide, issue templates). The Pet is an RPi build; the
  repo no longer advertises ports that haven't been written.

## [0.1.0] — 2026-04-18

First packaged release of the Pet as a standalone Python project.

### Added

- `src/cosmergon_pet/face.py` — the Pet script (Stufe 1 Pet-Modus): 8
  info-screens, rotary-encoder navigation, context menu, GPIO +
  luma.oled integration, `--simulate` mode for laptop development
- `src/cosmergon_pet/__init__.py` — package marker, `__version__`
- `pyproject.toml` — installable via
  `pip install git+https://github.com/rkocosmergon/cosmergon-pet`,
  exposes `cosmergon-pet` console script
- `install/requirements.txt` — runtime dependencies

### Moved

- Pet script from `cosmergon-agent/examples/rpi-pet/cosmergon_face.py`
  to `cosmergon-pet/src/cosmergon_pet/face.py`. The SDK repo keeps a
  redirect-README at the old path.

### Build guide

- **v1.4** (2026-04-18) — Install flow rewritten: one `pip install`
  line instead of three + curl. Agent starts via `cosmergon-pet`
  console script. systemd unit renamed to `cosmergon-pet.service`.
- **v1.3** (2026-04-18) — New **Schritt 1** "SD-Karte mit Raspberry
  Pi OS bespielen" (headless install via Pi Imager, WiFi + SSH +
  locale pre-configured). Existing steps shifted by one. Removed
  five-stage roadmap, teaching-context references and phantom links
  (STL cases, M5Stack firmware) — the repo now focuses on what
  actually exists. Added Troubleshooting section with five common
  real-world problems. `--simulate` flag documented.
- **v1.2** (2026-04-16) — Build guide aligned with concept document,
  8 info-screens, context-sensitive action menu, long-press semantics.
- **v1.1** (2026-04-16) — Shopping list moved to the end, table keep-
  together.
- **v1.0** (2026-04-16) — Initial build guide.

[Unreleased]: https://github.com/rkocosmergon/cosmergon-pet/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/rkocosmergon/cosmergon-pet/releases/tag/v0.1.0
