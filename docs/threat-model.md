# Threat Model — cosmergon-pet (LLM Layer)

**Status:** v1.0 (S158, 2026-05-02)
**Scope:** The pluggable LLM-provider layer in `src/cosmergon_pet/llm/` plus
the autonomous decision loop in `llm_decider.py`. Hardware base (RPi + OLED)
is out of scope here; see [`onboarding.md`](onboarding.md) for the physical
threat picture (theft, supply-chain of components, etc.).
**Audience:** Maintainers, security reviewers, auditors evaluating the
pet's autonomous behaviour for fitness in their own environment.

## Why this document exists

The pet started as a button-driven OLED display (S150). With S157 it gained
an autonomous LLM-decision mode that can read game-state from a Cosmergon
backend and submit actions on the player's behalf. That is a new attack
surface and a new privacy footprint. This page is the public companion to
the cosmergon-internal security panel (S157, items K1/E1/K2a/K2b/M1
applied, K3/M2 deferred).

The format follows STRIDE-per-element. Mitigations are cross-referenced to
the actual code paths so a reviewer can verify them with `grep`.

## Trust zones

| Zone | What's there | Trust |
|---|---|---|
| **Pet device (T-pet)** | RPi, OLED, GPIO, optional encoder, the python package itself, on-disk config (`~/.cosmergon/config.toml`), in-memory player token | trusted by the owner; **not** trusted by the network |
| **LLM provider (T-llm)** | Ollama (or future providers) — runs on owner's LAN by default | trusted enough to make recommendations, **not** trusted to act directly. `VALID_ACTIONS` allowlist sits between LLM and backend (S157 K1) |
| **Cosmergon backend (T-backend)** | Public REST API at `cosmergon.com`, owner-scoped via `X-Player-Token` | trusted to enforce ownership and rate limits server-side |
| **LAN (T-lan)** | Wi-Fi / Ethernet between pet and Mac Mini (where Ollama runs) | semi-trusted; assumed not adversarial in normal use, **not** assumed authenticated |

## STRIDE table

### Spoofing

| Threat | Mitigation | Code anchor |
|---|---|---|
| Attacker on the LAN poses as the LLM provider, returns crafted JSON | The decider never executes raw LLM output — only actions whose name appears in `VALID_ACTIONS` are forwarded to the backend (S157 K1) | `src/cosmergon_pet/llm_decider.py` — action allowlist |
| Attacker poses as the pet to the backend (steals X-Player-Token) | Token is held in memory only; on-disk file `~/.cosmergon/config.toml` is per-user mode `0600`. Backend rate-limits per token. | SDK `_token.py` (sensitive-string wrapper) |

### Tampering

| Threat | Mitigation | Code anchor |
|---|---|---|
| Modified python package on PyPI (typosquat / supply-chain) | Pet is not on PyPI yet — install is from `git clone` of this public repo. CI publishes via `installer e2e (Pi OS Lite aarch64)` test on every push | `.github/workflows/test-installer.yml` |
| Modified `~/.cosmergon/config.toml` (LLM URL, model) | Owner-only mode `0600`. A modified URL would point to a different LLM — the `VALID_ACTIONS`-allowlist mitigates "LLM tells pet to do something dangerous" |  |

### Repudiation

| Threat | Mitigation | Code anchor |
|---|---|---|
| Owner disputes that the pet performed an action | Backend logs every `/action` call in `agent_decisions` (cosmergon-internal) | Backend code, see cosmergon repo (private) |
| Owner cannot tell which decisions came from the LLM vs. button-press | `llm_decider` emits structured log lines with `source=llm` so a `journalctl -u cosmergon-pet` shows the chain | `src/cosmergon_pet/llm_decider.py` |

### Information Disclosure

| Threat | Mitigation | Code anchor |
|---|---|---|
| LLM logs leak action parameters (e.g. trade-target, amount) | `_redact_params()` strips `to_player_id`, `amount` and similar before logging (S157 E1) | `src/cosmergon_pet/llm_decider.py::_redact_params` |
| The LLM provider sees the player's full game state | **By design** — the LLM needs context to reason. Documented in [`autonomous-llm-mode.md` §Privacy](autonomous-llm-mode.md). Owner-controlled choice via `--llm-provider`. DSGVO Art. 13 disclosure note in same file. | [`autonomous-llm-mode.md`](autonomous-llm-mode.md) |
| Player token leaks via debug print / repr | `_SensitiveStr` in the SDK refuses to be printed or repr'd; pet pulls token through SDK | SDK `_token.py::_SensitiveStr` |

### Denial of Service

| Threat | Mitigation | Code anchor |
|---|---|---|
| Pet calls the backend in a tight loop | Background-loop has `--llm-interval-s` (default conservative); backend has slowapi rate-limit | `src/cosmergon_pet/llm_decider.py` background loop |
| LLM provider is slow / down | Background-loop catches timeouts and falls through to button-only mode for this iteration. No retry-storm. | `src/cosmergon_pet/llm/ollama.py` request-timeout |
| Ollama port (11434) exposed to the public internet | [`autonomous-llm-mode.md`](autonomous-llm-mode.md) **Network Exposure** section explains LAN-bind / firewall / Tailscale. Detection probe documented. | doc (no code) |

### Elevation of Privilege

| Threat | Mitigation | Code anchor |
|---|---|---|
| LLM crafts a payload that causes the pet to call admin endpoints | The pet's token is a player-scoped token, not an admin token. Backend authorises per-token; admin endpoints require a separate operator credential which the pet never holds. |  |
| LLM crafts an action with a different `agent_id` than the pet's | The decider forwards actions only as the pet's own agent — `agent_id` is not part of the LLM payload, it is taken from the pet's local state | `src/cosmergon_pet/llm_decider.py` |

## Open items

| # | Item | Status | Where |
|---|---|---|---|
| 1 | `whitelist-check.yml` runs on PRs but main accepts pushes that fail it (no branch protection) | Owner action: GitHub repo → Settings → Branches → require status checks before merging | github.com (settings) |
| 2 | The `VALID_ACTIONS` allowlist is hardcoded — could fall behind backend reality | Trade-off accepted: any new backend action requires a pet release. Pin the action set rather than have the pet trust whatever the backend sends. | `src/cosmergon_pet/llm_decider.py` |
| 3 | No signed releases yet | Pet is git-install-only today, signing matters once we publish to PyPI | tracked in cosmergon-internal TODO |

## Verification commands

```bash
# Action allowlist actually enforced?
grep -n "VALID_ACTIONS" src/cosmergon_pet/llm_decider.py

# Log redaction in place?
grep -n "_redact_params\|to_player_id" src/cosmergon_pet/llm_decider.py

# Privacy disclosure in user-facing doc?
grep -n "Privacy\|DSGVO\|GDPR" docs/autonomous-llm-mode.md

# Whitelist check in CI?
cat .github/workflows/whitelist-check.yml
```

## How to update

When a new LLM provider is added (e.g. OpenAI, Anthropic, local-llama):

1. Add the provider to `src/cosmergon_pet/llm/` following `base.py`'s contract.
2. Re-evaluate every row of the STRIDE table for the new transport
   (HTTP endpoint, API key handling, rate limit behaviour).
3. Add a paragraph to [`autonomous-llm-mode.md` Privacy](autonomous-llm-mode.md)
   describing the data flow to that provider.
4. Bump this doc's date in the header and link the PR.

## Cross-references

- [`autonomous-llm-mode.md`](autonomous-llm-mode.md) — user-facing setup,
  Privacy, Network-exposure
- [`SECURITY.md`](../SECURITY.md) — disclosure policy for security issues
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — code-style + PR checklist
