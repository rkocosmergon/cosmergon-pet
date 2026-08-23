# Changelog

All notable changes to Cosmergon Pet are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.8.3] — 2026-08-23

### Fixed

- **One mission at a time, respected client-side**: after a successful
  `start_mission` the loop pauses further starts (server enforces max 1;
  retries were guaranteed 422s that fed the failure backoff right when the
  chain was working). The decider's old `my_mission`/`marauder_state` guards
  were dead code — the SDK GameState never carried those fields; the guard
  now reads the server truth from `available_actions.start_mission.marauder_state`.

## [0.8.2] — 2026-08-23

### Fixed

- **start_mission never reached the wire correctly** (TreeDecider v2.2.2):
  the resolver returned `mission_type`/`reward_energy` at the top level, but
  the server's ActionRequest only knows `params` — Pydantic silently dropped
  the unknown fields and every start_mission (including the 0.7.0 scout
  fallback) died as 422 "mission_type required". Same error class as the
  v2.1.2 propose_from_template fix. All mission payloads now travel inside
  `params`; tests assert the wire contract, not the client-internal shape.

## [0.8.1] — 2026-08-23

### Fixed

- **The conquest chain is now reachable** (TreeDecider v2.2.1): a fieldless
  agent below the subsistence threshold was locked into the subsistence pool,
  where `market_list` was the only valid move (`place_cells` needs a field,
  `create_field` a free slot) — weeks of market carousel were a pool property,
  not a strategy. `start_mission` joins the subsistence pool (the chain costs
  no energy and is, next to `create_field`, the only sustainable income
  source); fieldless mission steps score 0.9 under `energy_at_least`.

## [0.8.0] — 2026-08-23

### Added

- **Conquest chain for fieldless agents** (TreeDecider): when the server
  provides the land-route facts (`available_actions.start_mission` /
  `.claim_field`, Cosmergon >= v1.64.143), a fieldless agent now loots the
  richest loot field for mega bombs (`gather_spores` needs no owned field)
  and sieges the first listed target at >= 3 bombs — the server spawns the
  follow-up capture itself. The S306 scout fallback remains for older servers.

## [0.7.0] — 2026-08-22

### Fixed

- **A field-less agent could no longer get back into the game.** Socket-hand had
  been at zero fields for over eight days — no field income, only decay, and
  42 `market_buy` decisions in 45 minutes. Two causes, both here:

  1. The terminal mission picked its destination from `universe_cubes` — the
     list filtered to cubes with a *free slot*, i.e. "where could I create a
     field". In a settled world that list is necessarily empty (measured:
     8 active cubes, the main-world ones at 128/128 fields), so `scout_terminal`
     fell back to `gather_spores`, which needs a field the agent does not have.
     Result: no mission at all. It now reads `reachable_cubes` — visiting a
     terminal needs no free slot.
  2. All four persona missions require owning a field. An agent with none now
     scouts regardless of persona: the terminal is what reveals vulnerable
     targets (`field_lookup`), and a capture follows from that. Ownership is the
     basis of existence, not a matter of style.

### Note

`claim_field` stays disabled on purpose. The verb has been dead project-wide
since S254/S263-W1 — conquest runs as a `capture_field` mission. And the target
list is deliberately **not** published in the agent state: reconnaissance is
bound to the terminal, so it costs presence.

Requires `cosmergon-agent >= 0.19.0`, but falls back to `universe_cubes` when
the server does not know the field.

## [0.6.0] — 2026-08-22

### Changed

- **Screen 1 now shows the energy balance over time instead of a text
  summary.** A line curve with hatched area underneath fills the panel, the
  agent's name sits at the bottom, the current balance top right. High and low
  of the visible range are marked with a triangle and their value. The window
  cycles every ten seconds: **60 minutes → 24 hours → 7 days** (founder
  request 2026-08-22).

  Line with vertical hatching rather than a solid fill: at one bit the two
  elements can only be told apart by DIRECTION, not brightness. The curve is a
  continuous horizontal run, the hatching a series of vertical strokes — so the
  hatching is drawn first and the line on top, otherwise every stroke would
  break the curve open. The curve connects column to column instead of setting
  points; on steep sections it would otherwise fall apart into dots.

  The high/low markers sit on a filled black patch so they stay readable over
  the hatching, and they sit on the LEFT: the curve ends on the right at the
  current value, which is the most important point on the screen.

  The curve is scaled to its own value range, not to zero: an account moving
  between 56.1k and 56.4k would otherwise be a flat line, and the movement is
  what the screen is for. When many points are squeezed into 128 columns, each
  column keeps the **peak** value, so a spike cannot be smoothed away.

  The triangles are drawn as polygons, not typed as characters: the Pi's
  default bitmap font has no U+25B2/U+25BC and renders a hex-code box instead
  (checked on the device).

- Requires `cosmergon-agent >= 0.18.0` for `get_balance_history()`.

### Note

The history is fetched every five minutes, separately from the other polls —
a 24-hour curve whose finest point is 15 minutes wide gains nothing from
faster polling, and the Pi is on Wi-Fi.

## [0.5.0] — 2026-08-22

### Added

- **Animated robot eyes on the OLED screensaver** (`cosmergon_pet.robo_eyes`).
  The idle screen no longer prints an ASCII face like `( ^__^ )` — it draws a
  pair of eyes that blink, look around, and change shape with the agent's
  state. The eyes are drawn parametrically, not from sprite images: a
  half-lowered lid is a number, so every in-between state exists without an
  extra asset.

  Behaviour follows the documented API of the **FluxGarage RoboEyes** Arduino
  library by Dennis Hoelscher (configurable size and spacing, four moods, eight
  gaze directions, autoblinker, idle motion, confused/laugh shakes, flicker).
  **No source code was taken from it.** RoboEyes is GPL-3.0 and this project is
  MIT, so a copy would have relicensed the published Pet; it also targets
  `Adafruit_GFX`, while the Pet draws through `luma.oled` and PIL. Behaviour is
  not copyrightable, implementations are.

- `scripts/preview-robo-eyes.py` renders a contact sheet and an animated GIF of
  every state, so the face can be reviewed without hardware.

### Changed

- The screensaver uses the **full 128×64 panel**. The 4-pixel cell-bar along the
  bottom edge is gone.
- Screensaver refresh rate raised from 10 to 20 Hz — at 10 Hz a 0.18 s blink is
  two frames and reads as a glitch. Measured hardware ceiling is 30.6 Hz
  (32.7 ms per I²C transfer on a Pi Zero 2 W).
- The OLED only transfers a frame when the image actually changed. Measured on
  the device: 105 rendered frames produced 11 distinct images, so roughly nine
  out of ten transfers are skipped. The higher frame rate therefore costs less
  bus time than the old 10 Hz unconditional redraw.
- The draw loop passes the agent **state** to the display instead of a finished
  face string. How that state looks is now the display's decision — the console
  simulation keeps its ASCII face unchanged.

### Note

`alert` and `action` cannot appear on the screensaver: it requires 30 s without
input, while those states last 0.8 s and 2.5 s *after* an input. Their eye
shapes exist as a fallback and are covered by a test that recomputes this from
the three timing constants.

## [0.4.4] — 2026-08-22

> **Note for PyPI users:** the previous published release was 0.4.0. Versions
> 0.4.1–0.4.3 were tagged in the changelog but never published, so installing
> from PyPI has been three versions behind — most notably without the social
> cadence from 0.4.3, which stops the once-per-minute proposal loop that pinned
> a live agent's reputation at the saturation floor. Installing from GitHub
> (the documented path in the README and installer) was unaffected. This
> release carries 0.4.1–0.4.4 together.

### Fixed

- **Both decision loops now obtain the game state themselves instead of
  assuming a caller supplies it — and say so when it is missing.** Reading
  `agent.state` without ever fetching it made "someone else keeps it fresh" an
  unwritten precondition. Inside the Pet that someone is `face.py`'s polling
  task, which mirrors every `/state` response into the SDK's private slot
  (`agent._state = state`) — a workaround added on 2026-05-04 after the LLM
  decider was found running on an empty `GameState`, where
  `_build_action_choices` collapsed to the `wait` line only.

  The precondition was never documented, and its absence was silent:
  `tree_loop` logged a DEBUG line and skipped the round, `llm_decider` passed
  `None` straight through and degraded to `wait`. Running either loop outside
  the Pet reproduces this at once — a container ran the tree loop for minutes,
  logged nothing beyond "started", and executed zero actions; only the server's
  records showed it.

  Both loops now use the new `agent_state.StateSource`: prefer a state someone
  else keeps fresh, fetch one via `agent.refresh_state()` when nobody does, and
  emit a single WARNING once it has been absent for three consecutive rounds
  (recovery is reported too). Inside the Pet nothing changes — the state is
  already present, so no extra request is made. Both loops are now usable
  standalone, without a Pet around them.

## [0.4.3] — 2026-08-15

### Fixed

- **Social cadence — a successful contract proposal now pauses both propose
  actions for 30 rounds.** The 0.4.2 duration fix only closed the *pact*
  revolving door: rejected partners remain server-side candidates, and a
  rejection arrives asynchronously *after* a `success=True` propose, so the
  failure backoff never sees it. Measured live (Comet-hand, 24 h): 992
  proposals at a once-per-minute cadence, 800 rejected, reputation pinned at
  the −1.0 saturation floor (each rejection books a penalty on the proposer).
  The cadence is derived, not guessed: the median decision interval of
  receiving agents is ~30 minutes — proposing faster than receivers can even
  decide structurally produces queue rejections. Both propose actions are
  paused together so the tree cannot sidestep via its template twin.

## [0.4.2] — 2026-08-14

### Fixed

- **TreeDecider v2.1.3 — contract `duration` 100 → 1000 ticks.** With
  ~2.5-hour pacts every expired partner immediately re-entered the candidate
  pool: 34 pacts in 75 minutes, a permanent revolving door. 1000 ticks is the
  main world's relationship timescale (capture cooldown), making the pact
  semantically real.

## [0.4.1] — 2026-08-14

### Fixed

- **TreeDecider v2.1.2 — `propose_from_template` params travel in the
  `params` sub-dict** (the SDK lays `act()` kwargs flat; the backend's
  `ActionRequest` drops unknown top-level keys → 422), and the tree only
  uses free-tier templates (T07/T08).
- **TreeDecider v2.1.1 — contract type and terms come from the backend's
  truth.** The tree invented `research_agreement` (no such backend type →
  156× HTTP 400) and sent `trade_agreement` without its required
  `fee_discount_pct` term.

## [0.4.0] — 2026-08-13

### Fixed

- **TreeDecider v2.1.0 — the tree no longer dead-loops on rejected actions.**
  Observed live on a fieldless, poor agent (Comet-hand): the tree retried the
  same rejected action every minute for days. Three root causes fixed:
  - `market_list` validity now reads the **server truth** from
    `available_actions.market_list` (`sellable_energy` / `sellable_items`,
    Cosmergon backend >= v1.64.30) instead of a local `energy >= 1500`
    threshold that contradicted the backend's coverage rule (an energy
    listing requires surplus above the decay exemption). Older backends
    fall back to the previous behavior.
  - `start_mission` no longer sends `reward_energy: 1000` — the backend
    rejects any self-created mission with a reward (you would be paying
    yourself out of nothing). It also never sends `None` UUIDs anymore:
    if no own field / no visible cube can fill the mission params, the
    action is simply not a candidate.
  - New **backoff** in `tree_decision_loop`: after 3 consecutive failures
    of the same action it is blocked for 30 rounds, so the tree picks its
    next-best option instead of hammering the API.

### Added

- **Covered inventory listings.** When the agent has no energy surplus but
  holds sellable inventory (e.g. mega bombs), the tree now lists one item,
  priced at 95 % of the cheapest active listing of the same type from the
  market briefing — never from a hardcoded price table.

## [0.3.0] — 2026-06-22

### Added

- **Contract-aware TreeDecider and LLM-Decider.** Both `decider_tree.py` and
  `llm_decider.py` now handle incoming contract proposals instead of ignoring
  them. `TreeDecider` adds a Layer 0 that pre-empts all other decisions when
  pending contracts are present, using a `PERSONA_CONTRACT_BIAS` map (6
  personas × 4 contract types) to accept or reject. `LLMDecider` extends
  `_build_action_choices` to surface each pending contract as an explicit
  `accept_contract` / `reject_contract` choice line so the LLM sees the offer
  in context. Both add `propose_counter` to their `VALID_ACTIONS` sets.
  Follows Cosmergon Founder Directive S204: "all agents may negotiate any
  contract type."

### Security

- Removed hardcoded internal LAN IP from `scripts/local-experiment.py`
  — changed argparse default to `localhost`.
- Abstracted private email pattern in `scripts/check-whitelist.sh`.

## [0.2.2] — 2026-05-12

### Added

- **`create_cube` is now a valid action** in both `decider_tree.VALID_ACTIONS`
  and `llm_decider.VALID_ACTIONS` allowlists. Pet was structurally blocked from
  proposing new-cube purchases even though the Cosmergon backend has supported
  this action for months and `expansionist` persona prompts it as a flagship
  move. Affordability gating (`can_afford_cube`) and coordinate resolution
  remain backend concerns. Empirie 2026-05-12: 0 `create_cube` decisions in
  24 h across all Pet-driven agents despite 78/150 having ≥ 500 k energy. (#28)

## [0.2.1] — 2026-05-09

### Fixed

- **Diplomat-persona `propose_contract` failed 100 % on Socket-hand (RPi 4).**
  TreeDecider v2.0.2 sent `terms = {"duration_ticks": 100}` but the Cosmergon
  backend validator (`contract_manager.validate_terms`) requires the API
  term-key `"duration"` (the name `duration_ticks` is the ORM column only —
  not the API field). Empirical anchor: Socket-hand 0/99 success in 24h
  before the fix. The backend simultaneously corrected the misleading
  error-hint that suggested `duration_ticks`.

## [0.2.0] — 2026-05-08

### Changed (BREAKING — Decider architecture replaced)

- **Re-vendored TreeDecider v1.1.4 → v2.0.2 (GOBT pattern).** Major
  architecture rewrite. The v1.x first-match-cascading tree was 4×
  empirically found to produce mono-action patterns
  (S170-hoarding, v1.1.2-race, v1.1.3-margin, v1.1.4-create_field-spree).
  Reactive iteration patches (action-cap, frequency-limit) explicitly
  rejected. v2.0.x uses GOBT (Goal-Oriented Behavior Tree, established
  game-AI pattern since ~2024).
- **Two-layer architecture:**
  1. **Subsistenz** (universal): when energy < persona-specific threshold,
     Pet earns energy via `place_cells` / `market_list` / `create_field`.
  2. **Persona-Kern-Charakter** (individual): 6 personas with their own
     life cycles, action pools, goal metrics, and bias maps:
     - scientist: experiment → wait-for-reife → evolve → publish → acquire → collab
     - trader: buy-low → sell-high → inventory-use → trade-agreements
     - warrior: territory → defense → diplomatic-pacts → evolve
     - expansionist: expand → minimal-fill → acquire
     - diplomat: network → goodwill → mediator → maintain
     - farmer: tend → evolve → sell-surplus
- **Generic score function** with goal-metric argument (8 internal
  predict_*_delta calculators).
- **Direction-based scoring (v2.0.1)**: actions in the right direction
  receive ≥0.7 score even at low magnitude — fixes Pulsar-eye-class
  pattern where +3 cells / 403 fields was scored 0.0003 absolute.
- **Bootstrap goal (v2.0.2)**: all personas at 0 fields use
  `field_count_at_least=1` first, before any persona-specific cycle —
  prevents cold-start where persona goal could not be reached without
  a field.
- **Persona-Bias additive** [-0.3, +0.3]. Goal logic dominant, persona
  shapes as tiebreaker.
- **Compass = additional bias modifier** [-0.2, +0.2].
- **Anti-hoarding preserved (v1.1.4 heritage)**: PERSONA_BUYABLE_TYPES
  filter on market_buy.
- **Race-margin preserved (v1.1.3 heritage)**: 15% safety margin on
  `_can_afford_field` against decide/execute Conway-tick drain.
- **Catastrophe-recovery implicit**: Subsistenz-layer-switch triggers
  automatically when Conway tick or Grey Plague lowers Pet energy.
- **Stateless, deterministic, sub-millisecond, explainable**: no
  action-history, no cycle counters, full decision trace via
  (persona, layer, goal_metric, score) per cycle.
- **NEW vendored file**: `src/cosmergon_pet/persona_profiles.py`
  (constants for all 6 personas + subsistenz logic).

### Concept

Reference: `docs/konzepte/konzept-decider-tree-v2.md` in the private
Cosmergon repo (5-voice panel + founder review 2026-05-08).

## [0.1.33] — 2026-05-08

### Fixed

- **`cosmergon_pet.__version__` string** was still `0.1.31` in 0.1.32 — the
  pyproject.toml bump was applied but the hardcoded `__init__.py` constant
  was missed. Cosmetic fix; no behaviour change. Skipped a destructive
  re-tag of v0.1.32, applied a clean v0.1.33 instead.

## [0.1.32] — 2026-05-08

### Changed

- **Re-vendored TreeDecider v1.1.1 → v1.1.4** — two empirically-driven fixes
  from the lab cluster (S171):
  1. **`item_type` filter on `market_buy` (anti-hoarding).** S171 finding:
     comet-hand bought preset listings 97.5 % of the time over 24 h with
     no follow-up usage — the `_can_keep_buying_cubes` cap only counts
     `state.universe_cubes`, presets land elsewhere and never trigger the
     cap. Fix: persona-specific `allowed_types` keyword on
     `_cheapest_buyable`. Default for scientist/expansionist/farmer/warrior/
     diplomat: `("cube", "field")`. Trader: `None` (all types allowed,
     market activity is core to the trader persona).
  2. **15 % safety margin on `_can_afford_field`.** S171 finding: tree
     read `available_actions["create_field"]["can_afford"]` at decide-time,
     but between decide and execute (90 s = 1–2 Conway ticks) field
     maintenance can drain energy below `next_cost`. Fix: check
     `energy >= next_cost * 1.15` instead of just `next_cost`. Catches the
     race window without changing first-field-free behaviour
     (`next_cost=0 * 1.15 = 0`).
- Both fixes touch all six persona create_field branches (S168 originally
  added `_can_afford_field` only to the BASE_TREE branch-2 zero-state-
  bootstrap path).

## [0.1.31] — 2026-05-07

### Changed

- **Re-vendored TreeDecider v1.1.0 → v1.1.1** — Anti-Hoarding cube-cap
  on `market_buy` (S170-Live-Befund: comet-hand kaufte 12+ cheap blueprints
  in Folge ohne sie einzusetzen, weil scientist[1] permanent matched).
  All personas now require `len(state.universe_cubes) < 5` before
  `market_buy` triggers. Once cap reached, the tree falls through to the
  next branch (typically `create_field`), which uses cubes up.

## [0.1.30] — 2026-05-07

### Changed

- **Re-vendored TreeDecider from cosmergon-decider-tree v1.0.0 → v1.1.0**.
  Three behaviour upgrades (S170 findings):
  - **Pattern-Tier-aware preset selection** — `place_cells` for empty fields
    now picks `blinker` (T1-oscillator → evolve-fähig) for scientist /
    expansionist / farmer personas, preserves `block` for warrior / trader /
    diplomat. Previous v1.0.0 hardcoded `block` for everyone, which created
    still-life dead-ends that could never evolve.
  - **Persona-Branches now have priority over empty-field-Refill** —
    survival-tunnel-vision fix. v1.0.0: empty_field always won over persona
    branches → rich agents (4.5 M E + many fields + 1 empty) made
    `place_cells` for many ticks before strategic actions could trigger.
    v1.1.0: persona branches (market_list, propose_contract, create_field,
    market_buy, evolve) match first when their energy thresholds (≥30 k to
    ≥100 k) are met; empty-field-Refill becomes the fallback when no
    persona-branch matches.
  - **Compass-Modulation extended** with `grow`, `cooperate`, `attack`,
    `explore` overrides (was: only `consolidate` + `defend`). Compass=None
    remains the default for Pet — these only fire when the user
    explicitly sets a compass-preset via SDK.

### Notes

- Pet vendoring header documents the v1.1.0 changes inline, so the file is
  self-contained for Maker users reading the Pet repo without access to the
  upstream decider-tree source.
- Cluster's `Pulsar-eye` lab-lane runs the same upstream — both reflect the
  same behaviour change in the next benchmark cycle.

## [0.1.29] — 2026-05-07

### Added

- **TreeDecider as autonomous-decision backend**, replacing the optional
  Ollama dependency for offline / edge deployments. New CLI flag
  `--with-tree-decider` switches the Pet's autonomous-decision loop from
  the LLM-provider path to a deterministic, rule-based persona-tree.
  Mutually exclusive with `--with-llm`. The tree mirrors the lab-cluster's
  tree-lane (Pulsar-eye) and runs in microseconds with zero external
  service dependency — Pet decides even when Ollama, network, or the
  lab-cluster is unavailable.
- Vendored `cosmergon_pet.decider_tree.TreeDecider` from the upstream
  `cosmergon-decider-tree` v1.0.0. Pure-Python rule logic, no model file,
  no inference. Sync policy documented in the module header.
- `cosmergon_pet.tree_loop.tree_decision_loop` — drop-in alternative to
  `llm_decision_loop` with the same lifecycle contract (stop-event,
  on_decision callback, exception-swallowing). Logs latency in ms (vs.
  the LLM path's seconds).

### Changed

- `run_pet()` accepts a new `tree_decider` parameter; raises if both
  `llm_provider` and `tree_decider` are passed.
- `__main__.py` `--with-llm` and `--with-tree-decider` are validated as
  mutually exclusive at argparse time.

## [0.1.28] — 2026-05-06

### Added

- **`propose_contract` in 6 personas** (S165). `VALID_ACTIONS` extended;
  `_build_action_choices` now surfaces one branch per
  `(target × free-tier contract_type)` for every counterpart in
  `state.world_briefing.contract_targets` (backend ≥ S165, SDK ≥ 0.12.0).
  Each branch pins `to_player_id`, `contract_type`, `terms`
  (`{duration_ticks: 100}`) and `escrow_amount=0` via JSON-Schema
  `const` so the LLM cannot invent UUIDs.
- **Persona-specific prioritisation** of `propose_contract`:
  - **diplomat:** prime move once `energy >= 10 000` (priority above market_buy)
  - **trader:** trade_agreement once `energy >= 30 000`
  - **scientist:** trade_agreement at `energy >= 50 000` (cooperation experiment)
  - **warrior, expansionist:** non_aggression at `energy >= 50 000` (free a flank)
  - **farmer:** non_aggression at `energy >= 80 000` (stable neighbours)
- 7 new tests in `test_llm_decider.py` (offered/skipped/cap/match-validation
  + persona prompt mention + diplomat priority order). Pet suite: 52 passed.

### Dependency

- `cosmergon-agent>=0.12.0` (required for the new
  `WorldBriefing.contract_targets` parser).

## [0.1.27] — 2026-05-06

### Fixed

- **`_build_action_choices` evolve-filter mirrors backend `_handle_evolve`
  fully.** Previously only `entity_tier in 1..4` was checked. The three
  additional gates (`reife_score`, `entity_type`, `balance`) were missing,
  so Pet offered evolve choices the backend rejected with HTTP 400. S164
  empirie on Comet-hand: 30/30 evolve calls in 3h failed with "Entity
  not mature enough" (28×) or "Pattern type does not match target tier"
  (2×). Pet's `_PERSONA_GUIDANCE` for scientist has Pfad-1 = evolve, so
  the LLM picked evolve deterministically on every cycle while the
  backend rejected every call. Direct verification with Comet-hand's real
  10-field snapshot: pre-patch `_build_action_choices` produced 6 evolve
  choices for 6 T1 fields, post-patch 0 (all six legitimately filtered:
  reife<100 or type=still_life when next_tier requires oscillator).
- **`__version__` drift fixed**: `__init__.py` was stuck at `0.1.18`
  while `pyproject.toml` had advanced through `0.1.26`. Both now in sync
  at `0.1.27`.

### Changed

- `_build_action_choices` evolve-row label now reads
  `evolve field_id=… (T{tier}->T{next_tier}, cost={cost} E)` instead of
  `… (current tier=N)`. Gives the LLM both the source and target tier
  plus the energy cost — informative for persona-sequence decisions
  ("scientist Pfad-1 evolve when offered" no longer fires blindly when
  cost would have failed).

### Why this matters

Comet-hand spent 3+ hours of S164-Vormittag spam-evolving fields the
backend rejected (~10 evolve attempts/hour, 100% failure rate, no Pet
self-learning because reflection-loop runs at lower frequency). LLM-level
fixes (schema mode v0.1.16, persona prompt v0.1.17, conditional
sequences v0.1.25, persona examples v0.1.26) couldn't break the loop
because Pet was offering an objectively un-takeable choice. The fix
moves the eligibility check to where it belongs: choice-construction,
not LLM persuasion.

### Tests

- Four new tests in `test_llm_decider.py` (analog face.py
  `_find_evolvable_field`):
  - `test_evolve_filtered_by_reife_threshold`
  - `test_evolve_filtered_by_entity_type_mismatch`
  - `test_evolve_filtered_by_insufficient_balance`
  - `test_evolve_offered_when_all_filters_pass`
- `_make_state` defaults updated so that all pre-existing tests stay
  green: `energy=1_000_000` (covers EVOLUTION_ENERGY_COST gate),
  `reife_score=100_000` (covers REIFE_THRESHOLDS gate), `entity_type`
  derived per tier from `_TIER_REQUIRED_TYPE_DEFAULT` (covers
  TIER_REQUIRED_TYPE gate). 45/45 Pet tests pass (pre-patch was 41/41).

### Pre-registered prediction (24h post-deploy)

- 0 backend-400 with "Entity not mature enough" or "Pattern type does
  not match target tier" for Comet-hand. Falsified if ≥1 → filter bug
  or timing race between Pet-state-snapshot and backend-state.

## [0.1.26] — 2026-05-05

### Added

- **Persona-specific decision examples** in `_build_system_prompt`. Each
  persona now demonstrates its top-3 sequence paths via concrete
  examples (scientist: evolve / market_list / create_field; trader:
  market_buy / market_list / place_cells; etc.). v0.1.25 conditional
  sequences alone were not enough to break Comet-hand's 100% place_cells
  bias (S162 4-iteration empirie). NB: empirically still ineffective on
  Comet-hand — the deeper root cause was the missing evolve filters,
  fixed in v0.1.27.

## [0.1.25] — 2026-05-05

### Changed

- **Persona-sequences sind jetzt conditional**, nicht linear-priorisiert.
  v0.1.24 hatte Sequences als (1) > (2) > ... > (6)-Listen. Empirie:
  Comet-hand 29× place_cells in 33min trotz `market_buy` als (4) im
  scientist-prompt — Position (4) wurde NIE erreicht weil (2)
  place_cells immer offered ist. Strukturelle Limitation des
  linear-Modells.
- Neues Format: `WHEN to act (pick the FIRST condition that matches): -
  IF energy >= 100000 AND any market_buy line is offered for under 2000 E:
  pick that. - IF ... - ELSE: pick wait.` Llama3.2:3b versteht
  plain-English-conditionals nachweislich (S160 NPC-Empirie 67%
  prompt-konform).
- Energy-Schwellen pro Persona spezifisch: scientist market erst bei
  100k, trader schon bei 30k, farmer market_list bei 50k.
- Persona-Identität bleibt — scientist priorisiert evolve+experiment,
  trader priorisiert market, warrior priorisiert territorial-grow.

### Notes

- Backend pendant: cosmergon v1.60.877 hat dieselbe conditional-syntax
  in `_get_preferred_actions()` (Backend-NPC-Pfad).
- Konzept-Stub mit 5-Phasen-Reform-Plan (L1-L5):
  cos20-repo `docs/konzepte/konzept-persona-system-reform-2026-05-05.md`.
  v0.1.25 ist L1-Pilot; L3 (persona-aware reputation) folgt nach 1 Wo
  Empirie.

## [0.1.24] — 2026-05-05

### Added

- **`expansionist` and `trader` personas** in `_PERSONA_GUIDANCE` —
  previously only scientist/warrior/diplomat/farmer had guidance blocks,
  unknown personas fell back to scientist. Comet-hand happens to be
  scientist; other Pets with these personas now get persona-appropriate
  sequences instead of scientist-fallback.

### Changed

- **All persona sequences now include `market_buy` and `market_list`** as
  numbered options. v0.1.22/23 had added these as schema choices, but the
  system-prompt sequences stayed at the 4-item `place_cells > evolve >
  create_field > wait` pattern from before market existed. Llama3.2:3b
  follows the persona-prompt exactly (S161 NPC empirie: 67% place_cells
  when prompt says place_cells first), so without market in the sequence
  the LLM never tried market — Comet-hand 7 h post-v0.1.23 had **0**
  market attempts despite 1.19 M E balance + offered choices.
- **`scientist` sequence reordered**: `evolve` is now (1), `place_cells`
  is (2). Matches backend NPC pattern; reminds the LLM that an evolve is
  a tier-jump (~doubles output) when one is offered.
- Per-persona market priority: scientist/farmer keep market low (4-5),
  warrior/diplomat mid (4), expansionist (2), trader (1-2). Persona
  identity preserved — scientist still primarily experiments, trader
  primarily trades.

### Notes

- Backend pendant: `cosmergon` v1.60.876 adds KAT-A Auto-Resolve in
  `_handle_market_buy` and `_handle_market_list` so an LLM that emits
  `market_buy {}` (without listing_id) gets the cheapest affordable
  listing auto-picked instead of a 422. NPC-side parallel fix.

## [0.1.23] — 2026-05-04

### Added

- **`market_buy` is now an offered action**, one schema-branch per
  affordable listing in `state.world_briefing.market.buyable` (backend
  ≥ v1.60.866). `listing_id` is rendered as a const so the LLM cannot
  invent UUIDs. Capped at 10 cheapest-affordable to keep 3B-LLM-Schemas
  small. Closes the S161 Wachstumspfad-Sprint Step 4 fully alongside
  Step 2b (NPC-MM cube tokens) — Pet can now actually buy what NPC-MM
  is selling.
- Bumped `cosmergon-agent` floor to `>=0.11.0` for the new
  `world_briefing.market.buyable` field.

## [0.1.22] — 2026-05-04

### Added

- **`market_list` is now an offered action** when the agent's energy
  exceeds 1500 E. Three price-tiers in the schema (400 / 450 / 500 E)
  let the LLM pick by urgency: 400 = vagant floor (moves fast), 500 =
  patient. Backend defaults `item_type='energy'` (S161 KAT-B), so Pet
  doesn't have to pass it. Trade tier of the Cosmergon S161
  Wachstumspfad-Sprint Step 4 — without `market_buy` (which needs
  dynamic per-listing schema branches and waits for NPC-MM cube
  liquidity per Step 2b).
- `VALID_ACTIONS` allowlist gains `"market_list"`.

## [0.1.21] — 2026-05-04

### Added

- **Pet now runs its own self-reflection** when the Cosmergon backend
  flags `state.reflection_due`. The flow: backend signals via the new
  v1.60.862 reflection-API → `_maybe_reflect` calls
  `agent.fetch_reflection_signals` → `provider.reflect` synthesizes
  lessons/avoid/double_down using the same llama3.2:3b that drives
  decisions → `agent.post_reflection` writes the result back as a
  `self_reflection` event with importance=1.0. Reflection runs BEFORE
  each decision so the very next memory-prompt picks up the lessons.
- `LLMProvider.reflect()` added to the protocol with default no-op
  fallback. `OllamaProvider` implements it via the structured-output
  mode that matches Cosmergon's `ReflectionResult` schema (lessons
  100-500 chars, avoid + double_down 50-200 chars).
- Bumped `cosmergon-agent` floor to `>=0.10.0` (needs the new
  `fetch_reflection_signals` + `post_reflection` SDK helpers).

### Why

Comet-hand and other api-Agents had been written into the Cosmergon
data store fine (self_decision + self_outcome + horizon_*-events) but
were systematically excluded from the in-Cosmergon reflection job
(`agent_memory_reflection.py::_FIND_AGENTS_SQL` filters on
`agent_mode='llm'`). Their "Your Past Lessons" memory-block stayed
empty forever — they collected experience but never synthesized lessons.
This release closes the gap without granting api-Agents access to a
Cosmergon-owned LLM (per memory directive
`feedback_non_npc_merken_und_externe_llm`): inference stays on Pet's
own Ollama, Cosmergon is data store + write target only. Reflection on
NPCs stays the in-backend path.

## [0.1.20] — 2026-05-04

### Fixed

- **`_poll_state` now mirrors the fetched GameState into the SDK's
  `agent._state`** so consumers that read `agent.state` (the LLM-Decider,
  third-party hooks) see the latest snapshot. Previously the custom
  polling loop only filled `ps.game_state` for the display while
  `agent._state` stayed `None`, because Pet runs its own polling instead
  of the SDK's `on_tick` driver. The LLM-Decider then read `None`,
  `_build_action_choices` collapsed to the single `wait` row, and the
  schema constrained the LLM to "wait" forever. Diagnosed 2026-05-04 via
  the prompt-dump introduced in v0.1.19: 3/3 captured rounds had
  `world="(no state available — agent not yet connected)"` while
  `/state` was returning 200 OK and `ps.game_state` was filled. Comet-hand
  chose 100% wait for ~33h despite the same llama3.2:3b choosing 67%
  growth as an in-Cosmergon NPC.

## [0.1.19] — 2026-05-04

### Added

- **Optional prompt-dump for diagnosis** — when the env var
  `COSMERGON_PET_PROMPT_DUMP_PATH` is set to a writable file path, every
  LLM decision round appends one JSONL line containing the exact 4-tuple
  passed to `provider.decide` (system_prompt, memory, world, schema) plus
  timestamp + agent_id. Off by default, no I/O when the env var is unset.
  Token-free by construction (player-token never enters this path).
  Designed for targeted comparison against an in-Cosmergon NPC LLM input
  when investigating divergent behaviour (e.g. why Comet-hand chose
  100% wait while the same llama3.2:3b chose 67% growth as an NPC).

## [0.1.18] — 2026-05-04

### Changed

- **`create_field` choices now cover the whole universe**, not just owned
  cubes. The Cosmergon backend permits any agent to add a field to any
  cube — cube ownership is an affiliate marker, not an access gate
  (S161 spec clarification). Pre-S161 the Pet only offered `create_field`
  rows for `state.cubes` (own cubes), which structurally locked Comet-hand
  and other newcomers without their own cube: they had no growth path,
  even though the backend would have accepted the call.
- **`_build_action_choices` now reads `state.universe_cubes`** (already
  exposed by the SDK / `AgentStateResponse.universe_cubes`). The S160
  hallucination concern that motivated the own-cubes-only restriction
  is structurally addressed by sourcing every cube_id from the backend
  response — the LLM cannot invent UUIDs because it can only pick from
  the rendered `oneOf`-list.
- **Situation block** now hints at universe-wide cube availability
  (`"Cubes you own: 0 — 30 cubes available universe-wide for create_field"`)
  when the agent owns fewer cubes than exist in the universe — gives
  the LLM a clear signal that growth via foreign cubes is allowed.

### Why this matters

Comet-hand sat with 1 field, 3 cells, max_reife 10818 (T2 oscillator) at
9990 E for 33+ hours, choosing `wait` repeatedly because the Pet's
schema-mode never offered him a path to grow. He has no own cube, so
`create_field` was structurally absent from his choice list. With this
change, Comet-hand sees every available universe cube as a valid target
the moment the next decision tick fires.

### Tests

- `test_format_world_no_create_field_when_universe_empty` (renamed)
- `test_format_world_lists_create_field_for_universe_cubes` (new — S161 use case)
- `test_format_world_create_field_when_only_own_cubes_present` (renamed,
  default mirroring of `cube_ids` to `universe_cube_ids` keeps it green)
- `_make_state` helper extended with `universe_cube_ids` parameter

## [0.1.17] — 2026-05-03

### Changed

- **Persona-aware system prompt.** Live empirics after v0.1.16 (Schema-
  Mode) showed Comet-hand chose `wait` 3/3 ticks while NPC llm-Agents
  chose `place_cells` 67% (155/225) over the same window. Schema was
  not the bottleneck — the Pet's system prompt was generic ("You are
  an autonomous agent"), while NPCs receive a persona-tone block plus
  a numbered preferred-action sequence ("(1) place_cells on lowest-cell
  field, (2) evolve, …, (6) wait"). Without that lenkung qwen2.5:7b
  rationally chose wait at 9988 E.
- **`_build_system_prompt(persona_type, agent_name)`** new in
  `llm_decider.py`: builds a persona-aware prompt mirroring the NPC
  pattern (`backend/app/core/personas.py::build_system_prompt`).
  Personas covered: scientist (default), warrior, diplomat, farmer.
  Each gets a tone sentence + 4-step preferred action sequence
  restricted to the Pet's `VALID_ACTIONS`.
- **`_one_decision`** now reads `state.persona_type` + `state.agent_name`
  (already carried by SDK `GameState` since 0.4.x) and passes the
  persona-aware system prompt to the provider, instead of a static
  module-level `SYSTEM_PROMPT`. Comet-hand (persona=scientist) now sees
  "You are Comet-hand, a scientist-persona agent" + scientist sequence
  + decision examples in the prompt header.
- **Tests** four new in `test_llm_decider.py`: persona+name in prompt,
  unknown-persona fallback to scientist, distinct tone per persona,
  end-to-end provider-call sees the persona-aware prompt. Pre-existing
  tests untouched (state mocks without persona_type still work via
  `getattr` default).

### Pre-registered prediction (verified after deploy)

- ≥1 successful `place_cells` in the first 5 ticks on cobot.
- wait-rate over 30 Ticks should drop from 100% (v0.1.16) to ≤50%.
- If both fail: fall back to model-swap experiment (qwen2.5:7b →
  llama3.2:3b, the NPC default — same chassis, smaller model that
  follows instructions more literally).

## [0.1.16] — 2026-05-03

### Changed

- **Ollama structured-output (JSON-Schema constraint).** All five
  prompt iterations from v0.1.11 through v0.1.15 attempted to teach the
  model "copy this line verbatim" via prompt wording alone — the model
  always found a way to ignore it (hallucinated UUIDs, hallucinated
  action names, empty params, etc.). Switched to Ollama's structured-
  output mode (`format: <JSON-Schema>` instead of `format: "json"`,
  available since Q1/2025): the schema enforces the action+params
  combination at decoder level — wrong tokens simply cannot be sampled.
- **`_build_decision_schema(choices)`** new in `llm_decider.py`: per
  tick, builds a `oneOf` schema with one branch per offered choice,
  every parameter pinned via `const` to the exact UUID/value from the
  choice. The model is structurally forced into one of N exact JSON
  outputs.
- **`LLMProvider.decide(..., schema=None)`** protocol extended (back-
  compatible default): providers that support structured output (Ollama
  today; future OpenAI/Anthropic adapters) consume the schema; legacy
  providers ignore it.
- **`OllamaProvider.decide`** passes `format=<schema>` when supplied,
  falls back to `format="json"` otherwise.

### Background

S160 v6 — the structurally correct fix. Five iterations of prompt
engineering were a detour; the right tool was Ollama's structured-output
since Q1/2025. With a `oneOf` schema constraining both action and every
param value, the model cannot return `{"action":"place_cells","params":{}}`
because that JSON shape simply isn't in the schema. The local
`_is_action_in_choices` filter remains as defense-in-depth (in case a
provider lacks schema support).

Pre-registered: ≥ 1 successful POST /action in the first 3 ticks. If
that fails, the bug is elsewhere (Ollama version, schema rejection,
or model-server adapter).

## [0.1.15] — 2026-05-03

### Changed

- **Each numbered line in the Available-Actions list IS the JSON.**
  v0.1.14 used a `Label` line followed by `→ {json}` continuation.
  qwen2.5:7b on Comet-hand parsed the structure as „pick action name
  from label, build my own JSON" — output `{"action":"place_cells",
  "params":{}}` (action name copied, params dropped). Filter dropped
  3/3 attempts. New format puts the JSON object directly on each
  numbered line followed by a `// human-readable comment`. Prompt now
  explicitly says „output exactly one of these lines verbatim — nothing
  else." Removes the option for the model to recompose JSON.
- SYSTEM_PROMPT „How to answer" rewritten for the new format.

### Background

S160 v4 (NPC-pattern adoption) successfully broke the 100 % wait
deadlock — qwen2.5:7b started picking `place_cells`. But it dropped the
params, suggesting the two-line label/JSON format invited the model to
"interpret" the action and recreate JSON. v5 collapses to one-line-per-
choice with the JSON as the only thing the model needs to copy.

Pre-registered for 30 ticks on Comet-hand:
  - ≥ 1 successful POST /action (i.e. an action that passes the local
    `_is_action_in_choices` filter and reaches the backend)
  - ≥ 30 % non-wait rate

## [0.1.14] — 2026-05-03

### Changed

- **SYSTEM_PROMPT adapts the NPC-prompt pattern.** Backend NPCs (which
  share Ollama with the Pet) have been making real game decisions for
  months while the Pet's autonomous mode chose 100% wait across v0.1.11
  through v0.1.13 — same models, very different prompt structure.
  Adopted from `backend/app/core/llm_agent.py::_build_user_prompt` and
  `personas.py::build_system_prompt`:
  - Imperative framing ("Every ~60 seconds you must take a turn. You
    decide what to do") replaces the passive "Output a single JSON
    object" header.
  - Concrete decision examples (healthy / mature / low-energy) modeled
    on NPC prompt's `_get_examples` block.
  - Tier-up requirements now spelled out in-prompt (oscillator → T2,
    spaceship → T3, gun → T4, breeder → T5).
  - Wait-clause sharpened: "rarely the right choice for a healthy agent"
    + concrete preconditions.
- **`_format_world` ends with "What is your move?"** — explicit prompt
  turn-taking, mirroring NPC's "Was tust du?". Pet was missing the
  conversational close that asks the model to commit.
- **Persona/identity prefix in world block** when state carries them:
  "You are Comet-hand, a scientist-persona agent." The NPC prompt has
  this at the top via `build_system_prompt(persona, agent_name, ...)`;
  the Pet was anonymous to its own LLM.

### Background

S160 Pet-LLM-Iteration v4. The walkthrough through three previous
iterations (v0.1.11 action-list, v0.1.12 JSON-snippet, v0.1.13 trigger-
info) plus modell-Switches (qwen2.5:7b, qwen3:14b) and the verified
backend memory fix all left the same symptom: 100% wait. The empirical
counter-example: NPCs use the same Ollama instance with the same models
and produce dozens of actions per hour. The structural difference is
the prompt, not the model.

This release ports the highest-value pieces of the NPC prompt pattern
without bringing in the full NPC-only machinery (no learned-rules,
no strategy-summary, no skills system — those need their own data
sources that the Pet doesn't have today).

Pre-registered for 30 ticks on Comet-hand:
  - ≥ 1 non-wait decision in the first 10 ticks
  - ≥ 30 % non-wait rate over 30 ticks
  - if still 100 % wait: the Pet-LLM mode is structurally ill-suited to
    this game state (a free-tier newcomer with one 3-cell field and
    9988 E is genuinely a "wait is rational" position). Next step would
    be either a richer game situation or accepting passive Pet behavior
    by design until conditions change (catastrophe, market opportunity).

## [0.1.13] — 2026-05-03

### Changed

- **World-Block zeigt jetzt Trigger-Info aus `world_briefing.situation`.**
  Bislang sah der LLM nur Energy-Snapshot + Field-Count → keine Notwendigkeit
  zur Aktion erkennbar. Empirie qwen2.5:7b und qwen3:14b: 100% wait über
  20+ Ticks bei Comet-hand mit 9988 E (Decay zog tatsächlich Energy weg,
  aber das Signal fehlte im Prompt). Neu im World-Block:
  - `Energy: X E (trend: rising/stable/declining)` — Backend liefert das
    via `agent_situation.energy_trend`, Pet verwendete es bisher nicht
  - Per-Field-Detail: `T<tier> <entity_type>, <N> live cells` — lässt das
    Modell Tier-Up-Eligibility (T2 oscillator → T3 needs spaceship)
    selbst nachvollziehen
  - `(N empty — losing income)` Hinweis bei leeren Fields
  - `⚠ Active catastrophe`-Banner bei Bedrohung
- **SYSTEM_PROMPT-Strategie geschärft**: explizit „Wait does NOT preserve
  the status quo — a passive agent slowly loses energy and eventually
  dies." Plus konkrete Wachstums-Mechanik („Tier-up roughly doubles
  output", „larger live-cell count → more energy"). Wait-Default-Position
  reframed: nur wenn nichts hilft, nicht „nichts dringendes".

### Background

S160 Pet-LLM-Iteration v3. v0.1.12 fixte Halluzinationen (kontextuelle
Action-Liste + JSON-Snippet pro Zeile). Backend v1.60.850 fixte den
Memory-Schreibpfad (isolated session — verifiziert in DB). Trotzdem:
qwen2.5:7b wählte 100% wait — strukturell rational, weil im Prompt kein
Signal stand das wait unattraktiv macht. v0.1.13 macht den Verlust durch
Decay sichtbar und gibt dem LLM Trigger zum Handeln.

Pre-registered für 30 Ticks an Comet-hand:
  - ≥ 1 non-wait Decision in den ersten 10 Ticks
  - ≥ 30 % non-wait Rate über 30 Ticks
  - falls < 30 %: Hypothese „Prompt-Trigger-Lücke" widerlegt — dann
    liegt es entweder am konservativen Modell-Default oder
    an der Spielmechanik selbst (passive agents existieren by design).

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
