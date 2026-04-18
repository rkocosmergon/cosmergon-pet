# Changelog

All notable changes to Cosmergon Pet are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `SECURITY.md` — vulnerability reporting policy
- `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1
- `CONTRIBUTING.md` — PR guide and style
- `CHANGELOG.md` — this file
- `LICENSE`, `LICENSES/MIT.txt`, `LICENSES/CC-BY-SA-4.0.txt` — dual
  license (MIT for code, CC-BY-SA-4.0 for docs), REUSE-compliant
- `NOTICE` — trademark usage guidelines

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
