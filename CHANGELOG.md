# Changelog

All notable changes to Cosmergon Pet are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.12] — 2026-05-03

### Fixed

- **SYSTEM_PROMPT-Beispiel triggerte Halluzinationen.** v0.1.11 hatte
  ein JSON-Beispiel mit `"field_id": "<id-from-list>"` als Platzhalter.
  Llama3.2:3b interpretierte die spitzen Klammern nicht als
  „setze hier eine ID aus der Liste ein", sondern kopierte den
  Platzhalter wörtlich. S160-Empirik zeigte zwei direkte Beweise:
  - Tick 17:08:03: `field_id='<uuid_from_list>'` 1:1 vom Beispiel
  - Tick 16:48:44: `field_id='<5f0e77c3-…>'` mit übernommenen Klammern
  Beispiel-Block komplett entfernt; Output-Regeln verweisen jetzt
  auf den per-Zeile vorbereiteten JSON-Snippet (siehe Added).
- **Wait-Bias-Fix.** v0.1.11 sagte „If nothing useful to do, choose
  wait" — eine zu offene Einladung. Nach 28 Ticks an Comet-hand:
  25 wait, 3 off-list-Drop, 0 success. Reformuliert zu „Prefer an
  active option that improves your situation; choose wait only when
  no listed action would help."

### Added

- **JSON-Snippet pro Choice-Zeile.** `_build_action_choices` rendert
  jetzt zusätzlich ein `json`-Feld pro Eintrag — die exakte
  JSON-Repräsentation, die der LLM für diese Zeile ausgeben soll.
  `_format_world` zeigt es direkt unter dem Label:
  ```
   1. place_cells   field_id=cb6e823b-…  preset=block
      → {"action":"place_cells","params":{"field_id":"cb6e823b-…","preset":"block"}}
  ```
  3B-Modelle müssen damit nur noch eine Zeile literal kopieren — keine
  UUID-Substitution, kein Format-Würfeln. SYSTEM_PROMPT-Regel 2 sagt
  explizit „copy verbatim, including every UUID character, no
  abbreviation, no angle-brackets".

### Background

S160 Iteration #2. Empirisch zeigte v0.1.11 nach 28 Ticks 0 Success
und 25/28 wait. Smoking-Gun-Befund war ein wörtlich kopierter
Platzhalter aus meinem eigenen JSON-Beispiel — Modell-Capability war
also nicht der Hauptengpass, mein Prompt-Design war es. Pre-Registered
v0.1.12: ≥ 50 % Non-wait-Decisions in 30 Ticks; 0 Drops mit
`<…>`-Pattern; ≥ 1 Success.

## [0.1.11] — 2026-05-03

### Changed

- **LLM-Prompt: kontextuelle Action-Liste statt statischer Aktionsbeschreibung.**
  Der `_format_world`-Block enthält jetzt eine numerierte Liste *konkret
  verfügbarer* Aktionen mit echten field_ids/cube_ids/Presets aus dem
  `/state`-Response. `SYSTEM_PROMPT` sagt dem Modell explizit „NEVER
  invent UUIDs — copy from list". Hintergrund: Empirie an Comet-hand
  zeigte 0/9 Success-Rate über 22 Min mit Llama3.2:3b — das Modell
  würfelte cube_ids und field_ids (z.B. `12345678-1234-1234-1234-...`),
  weil der vorherige Prompt zwar die Aktionen *nannte* aber das Modell
  nicht zwang, IDs aus dem Welt-Block zu kopieren. 3B-Class-Modelle
  folgen einer expliziten kopierfähigen Liste deutlich zuverlässiger
  als „benutze bitte die ID von oben".

### Added

- **`_build_action_choices(state)`** — Single Source of Truth für die
  Liste verfügbarer Aktionen in dem aktuellen World-State. Berücksichtigt:
  - `place_cells × {jedes Field} × {jedes affordable Preset}`
  - `evolve × {jedes Field mit entity_tier 1..4}` (T5 ist Maximum)
  - `create_field × {jeder eigene Cube}` — Newcomers ohne eigenen Cube
    sehen das gar nicht erst
  - `wait` (immer)
  Wird von `_format_world` für die Prompt-Darstellung *und* von
  `_one_decision` für die Post-Decision-Validierung benutzt — Prompt
  und Validator können nicht mehr divergieren.
- **`_is_action_in_choices(action, params, choices)`** — Defense-in-Depth
  Layer 2: nach VALID_ACTIONS-Check (S157 K1) wird jetzt zusätzlich
  geprüft, ob `(action, params)` exakt einem angebotenen Listen-Eintrag
  entspricht. Halluzinierte UUIDs werden lokal gedropt und nie an die
  Cosmergon-API geschickt — spart 404/422-Rauschen und gibt dem
  `wait`-Fallback nächsten Tick einen sauberen Start.

### Fixed

- **Latenter Bug:** `_format_world` las `state.energy_balance` — das
  SDK-Attribut heißt `state.energy`. Effekt: jeder LLM-Prompt hat
  buchstäblich `Energy: ?` enthalten (silent via `getattr`-Default).
  Beim Refactor mit-gefixt.

### Background

S160 Pet-LLM-Aktivierung an Comet-hand zeigte: das Modell halluziniert
verlässlich UUIDs trotz expliziter Field-ID im Welt-Block. Strukturfix
ist die kopierfähige Liste — keine semantische „use IDs from above"-
Bitte. Pre-Registered: ≥ 60 % Success-Rate in 24 h Beobachtung.

## [0.1.10] — 2026-05-01

### Fixed

- **Evolve-Menü zeigte falsche Kosten und falschen Tier-Begriff.** Vor
  diesem Fix nutzte das Menü `state.ranking.player_tier` (= Account-
  Ranking Novice/Bronze/…) als Eingabe für die Kosten-Heuristik
  `500 × 2^(tier-1)`. Beide Werte waren falsch:
  1. Server-Cost wird per `field.entity_tier` (Conway-Pattern-Tier)
     berechnet, nicht per Player-Ranking.
  2. Server-Cost ist 1.000 / 5.000 / 25.000 / 100.000 E pro Tier-Up,
     nicht 500 / 1.000 / 2.000 / …
  Effekt: Der User sah "Evolve (~500 E)", der Server zog 1.000 E ab.
  Bei Tier-Up auf T3 sah man 1.000 E, real wurden 5.000 E abgezogen.
- **Evolve-Aktion ging blind auf `state.fields[0]`.** Wenn das erste
  Field nicht evolve-fähig war (Reife zu niedrig, falscher Pattern-Typ,
  bereits T5), kam der Server-Call mit 400 zurück statt das richtige
  Field zu treffen. Jetzt prüft `_find_evolvable_field` alle Felder
  gegen die vier Server-Kriterien (entity_tier 1-4, reife ≥ Threshold,
  entity_type matched, energy ≥ cost) und wählt das erste passende.

### Added

- **Screen 7 (Last Action) zeigt User-Klicks UND LLM-Decisions parallel.**
  Vor diesem Release zeigte der Screen nur LLM-Decisions aus
  `/decisions`. Bei agent_mode=api (Pet-Default) gibt es keine
  LLM-Decisions → Screen war "No decisions yet." trotz aktiver
  Encoder-Klicks. Jetzt:
  ```
  You OK evolve
      -1000E free
  ---
  LLM:place_c ok
  ```
  Status-Marker: `OK` (Server 200), `!!` (Server-Fehler oder Exception),
  `..` (Aktion übersprungen, z.B. kein evolve-fähiges Field gefunden).
  Detail zeigt Energy-Cost + free-re-evolution-Marker, oder Tier-Up,
  oder Server-Fehlermeldung (max 18 Zeichen).
- Server-Cost-Konstanten (`EVOLUTION_ENERGY_COST`, `REIFE_THRESHOLDS`,
  `TIER_REQUIRED_TYPE`) als Mirror in `face.py` mit Source-Code-Kommentar
  zur Server-Tabelle (`backend/app/core/entity_tiers.py`). Müssen bei
  Server-Änderungen synchron gepflegt werden.

### Implementation

- `_find_evolvable_field(state, energy)` neue pure Helper-Funktion,
  ersetzt `_tier_up_cost` (gelöscht).
- `_summarize_user_action(label, result, now)` baut Pet-Display-
  Summary aus `ActionResult.success` + `data` + `error_message`.
- `PetState.last_user_action: dict | None` neuer Slot mit Schema
  `{action, status, detail, ts}`.
- `_render_last_action` zeigt User-Action + LLM-Decision parallel
  oder fallback "No actions yet." wenn beide leer.

### Background

S157 Forensik (Comet-hand-Field auf Prod): zwei Encoder-Klicks
verbrauchten je 1000 E ohne sichtbares Pet-Feedback, weil der
Engine-Tick das Field nach jedem Tier-Up zurück devolved hat. Der
darunterliegende Backend-Bug (S111-Latent-Bug bei JSONB-Persistenz
von `max_tier_paid`) wurde im Backend separat gefixt. Diese Pet-
Release behebt die User-Experience-Seite — falsche Cost-Anzeige und
fehlende Outcome-Sichtbarkeit.

## [0.1.9] — 2026-04-30

### Added

- **Screensaver eye blinks tied to backend polls.** The big face is no
  longer static — every successful poll triggers a 300 ms eye-blink
  on the screensaver:
  - `state` poll (every 30 s) → **left eye** opens wide: `( o__X )`
  - `events` poll (every 45 s) → **right eye** opens wide: `( X__o )`
  - `decisions` poll (every 90 s) → **both eyes squint** (action style):
    `( >__< )`
  Priority decisions > events > state, so a rare decision-blink always
  wins over the more frequent state/events ones. The base mood face
  underneath flows through unchanged. Build feedback: a static face
  feels dead on a desk; small irregular blinks tied to real backend
  activity make the Pet feel alive without being hectic.
- **Cell-bar at the bottom of the screensaver.** One small dot per
  active cell across all owned fields (max 30 dots, centred). Visually
  shows the agent's territorial activity at a glance, even when no
  detail screen is shown. 0 cells → no bar.

### Implementation

- `PetState` gains `last_state_poll_at` / `last_events_poll_at` /
  `last_decisions_poll_at` timestamps, set by the three pollers when
  a request succeeds.
- `apply_blink(face, ps, now)` — pure function, returns a modified
  face string for the 300 ms window after each poll.
- `OledDisplay.draw_big_face(face, cell_count)` — face area trimmed
  to 60 px so the 4 px cell-bar at the bottom never overlaps the face.
- `_draw_cell_bar()` — `Any`-typed `draw` argument for luma-canvas
  compatibility, dot size 3×2 px with 1 px gap.

### Tunables

- `SCREENSAVER_BLINK_DURATION` = 0.3 s
- Cell-bar geometry hard-coded in `_draw_cell_bar` (3×2 px dots, 1 px
  gap, 30 dots max — fills 119 px on the 128 px panel).

## [0.1.8] — 2026-04-30

### Changed

- **Screensaver font is now adaptive.** Replaces the fixed 32 px from
  v0.1.7 (which clipped the parentheses on a 128 px panel) with an
  auto-shrink loop: starts at 40 px and steps down until `( ^__^ )`
  measured via `getbbox` fits the display width minus a 2 px safety
  margin on each side. Result: as large as possible, never clipped.
  Tries DejaVu Sans Mono Bold → DejaVu Sans Mono → Liberation Mono
  Bold first (TrueType, crisp at any size), falls back to the Pillow
  Bitmap default and finally the 8 px default if the host has no
  TrueType fonts at all.

### Fixed

- **CI lint UP024.** v0.1.7 had `except (OSError, IOError)` — IOError
  is a Python 3 alias for OSError, the tuple is redundant. Replaced
  with plain `except OSError`. CI Python-lint workflow is back to green.

## [0.1.7] — 2026-04-30 (CI lint fail, superseded by 0.1.8)

### Changed

- **Screensaver face is now bigger and crisper.** Font size 24 → 32 px
  and the renderer now prefers DejaVu Sans Mono Bold (TrueType) over
  the Pillow Bitmap default. Bitmap default scales pixelated above
  ~16 px; the TrueType fallback chain (`DejaVuSansMono-Bold` →
  `DejaVuSansMono` → `LiberationMono-Bold`) ships with Raspberry Pi OS
  Lite by default. Monospace matters here so `( ^__^ )` keeps its
  shape — proportional fonts would squeeze the underscores and
  stretch the parentheses. Build feedback: 24 px felt small on a desk,
  32 px monospace fills the panel.

### Fixed

- *(NOT in this release — see 0.1.8)*: 32 px clipped parentheses on
  a 128 px panel; CI lint failed on `(OSError, IOError)` tuple.

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
