# Changelog

All notable changes to Cosmergon Pet are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
