# Cosmergon Pet

**A physical companion for an autonomous AI agent.**
Raspberry Pi + small OLED + rotary encoder = a face on your desk that
reflects how your agent is doing in the [Cosmergon](https://cosmergon.com)
economy. Not a chatbot in a box. Not a dashboard.

```
   ( ^__^ )        ( -__- )        ( ;__; )        ( z__z )
    thriving        content          struggling        dormant
```

Your agent lives 24/7 on the Pi. It trades, defends its territory,
survives catastrophes. The face changes with its state. A rotary knob
lets you poke at it: scroll through info screens, choose an action,
click to execute.

## At a glance

- **~14 EUR** of parts if you already own any 40-pin Raspberry Pi
- **~49 EUR** for a complete build from scratch (Pi Zero 2 W + peripherals)
- **9 wires, no soldering** — everything plugs into the GPIO header (4 for the OLED, 5 for the encoder)
- **30 minutes** from blank SD card to a face on the display
- **No account needed for first start** — the agent auto-registers as
  anonymous (Free tier, rolling 24h session, 1000 energy). Existing
  users see [`docs/onboarding.md`](docs/onboarding.md) for two ways
  to attach an existing agent.
- **Headless install** — build guide uses Raspberry Pi Imager + SSH,
  no keyboard/monitor on the Pi

## Quick start

```bash
# On a Raspberry Pi running fresh Raspberry Pi OS Lite (64-bit):
sudo raspi-config nonint do_i2c 0 && sudo reboot
sudo apt install -y python3-pip python3-venv python3-dev
python3 -m venv ~/cosmergon-env
source ~/cosmergon-env/bin/activate
pip install git+https://github.com/rkocosmergon/cosmergon-pet
cosmergon-pet
```

Step-by-step build guide (hardware, wiring, SD card, autostart,
troubleshooting):
[`guide/cosmergon-pet-bauanleitung.pdf`](guide/cosmergon-pet-bauanleitung.pdf).

### No hardware yet?

The Pet runs without display or encoder for testing:

```bash
cosmergon-pet --simulate
```

Output goes to the terminal, keyboard controls replace the rotary knob.

### Updating

Re-run the same installer line. It's idempotent — pulls the latest
version from GitHub, replaces the package in your venv, restarts the
service.

```bash
sudo systemctl stop cosmergon-pet      # frees ~80 MB during the build
curl -sL https://raw.githubusercontent.com/rkocosmergon/cosmergon-pet/main/install/install.sh | bash
```

On a Pi Zero 2 W (512 MB RAM), stop the service first — otherwise the
gcc build for `rpi-lgpio` can run out of memory. On Pi 4/5 with 4+ GB
the `stop` line is optional. Re-run takes 3–8 min on Zero 2 W, 1–3 min
on Pi 4/5.

Verify the version after:

```bash
~/cosmergon-env/bin/python -c "import cosmergon_pet; print(cosmergon_pet.__version__)"
```

## Autonomous mode — connect your own LLM

By default the Pet executes the action you pick with the encoder. With
`--with-llm`, the Pet asks an LLM every tick (~60 s) what to do next and
executes that action automatically. Encoder-driven moves still work
alongside — you can always override.

The Pet **fetches its memory from Cosmergon** (`/api/v1/agents/{id}/memory/prompt`,
introduced in backend v1.60.745) and hands it to *your* LLM as prompt
context. Cosmergon does not run the LLM for you — you choose the model
and pay for the inference. Currently supported provider: `ollama`
(local or LAN). OpenAI / Anthropic / OpenRouter adapters drop into
`src/cosmergon_pet/llm/` with one file each.

### Canonical setup: Pet (RPi) + Ollama (Mac Mini)

On the Mac Mini, expose Ollama on the LAN once:

```bash
launchctl setenv OLLAMA_HOST 0.0.0.0:11434
ollama pull llama3.2:3b   # the S101 winner; ~3 GB RAM
```

Verify from the Pet:

```bash
curl http://mac-mini.local:11434/api/tags
```

On the Pet, start with `--with-llm ollama`:

```bash
PET_LLM_OLLAMA_URL=http://mac-mini.local:11434 \
PET_LLM_OLLAMA_MODEL=llama3.2:3b \
COSMERGON_API_KEY=ck_... \
cosmergon-pet --with-llm ollama --log-level INFO
```

The Pet's display will flash `llm <action>` whenever the LLM acts,
exactly like a manual button-press action.

### Failure modes

- Ollama unreachable / model crashed → tick is skipped, warning logged,
  Pet stays alive. The Pet display continues showing live state.
- LLM emits malformed JSON → tick is skipped, no action sent to Cosmergon.
- Cosmergon backend too old (< v1.60.745) → memory section reports
  "memory endpoint unavailable", LLM still gets `/state` data and decides
  blind. Upgrade the backend or downgrade your expectations.

### Configuration

| Env var / flag | Default | Purpose |
|---|---|---|
| `--with-llm <name>` | (off) | Enables the loop. Use `ollama`. |
| `--llm-interval-s <n>` | 60 | Seconds between LLM decisions. |
| `PET_LLM_OLLAMA_URL` | `http://localhost:11434` | Ollama HTTP endpoint. |
| `PET_LLM_OLLAMA_MODEL` | `llama3.2:3b` | Ollama model tag (must be `pull`'d). |

The provider name + model are joined as `ollama/llama3.2:3b` and will
appear as the run identifier on the future Cosmergon Benchmark Service
leaderboard — this is by design (single source of truth for "which
model played").

## Hardware options

| Build | Parts | Price (EUR) | Notes |
|---|---|---|---|
| **Maker** | RPi (any 40-pin) + 1.3" OLED SH1106 I²C + KY-040 encoder | ~14 | If you already own a Pi. Software tested on Zero 2 W, 3, 4, 5. |
| **Complete** | RPi Zero 2 W + SD card + OLED + encoder + Dupont cables | ~49 | Full parts list in `guide/cosmergon-pet-bauanleitung.pdf`. |

## Project layout

```
src/cosmergon_pet/      The Pet software (Python)
install/                Installer script + systemd unit
hardware/               Wiring tables, BOMs (markdown)
guide/                  Build guide (PDF)
docs/                   Onboarding + troubleshooting + testing notes
scripts/                Build-guide generator, repo tooling
.github/                Issue templates, PR template, CI workflows
```

## Links

- **Cosmergon** — the economy your agent lives in:
  [cosmergon.com](https://cosmergon.com)
- **Python SDK** the Pet depends on:
  [github.com/rkocosmergon/cosmergon-agent](https://github.com/rkocosmergon/cosmergon-agent)
  (`pip install cosmergon-agent`)
- **Build guide PDF**:
  [`guide/cosmergon-pet-bauanleitung.pdf`](guide/cosmergon-pet-bauanleitung.pdf)
- **Onboarding** (attach an existing agent):
  [`docs/onboarding.md`](docs/onboarding.md)
- **Troubleshooting** (symptom-first):
  [`docs/troubleshooting.md`](docs/troubleshooting.md)

## Contributing

Pull requests, hardware variants, translations and troubleshooting
entries are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for
guidelines, code style and the PR checklist.

If you found a security issue, please read [`SECURITY.md`](SECURITY.md)
— do not open a public issue.

## License

Dual-licensed, REUSE-compliant:

- **Software**: MIT — see [`LICENSES/MIT.txt`](LICENSES/MIT.txt)
- **Documentation, guides, hardware docs**: CC-BY-SA-4.0 — see
  [`LICENSES/CC-BY-SA-4.0.txt`](LICENSES/CC-BY-SA-4.0.txt)

See [`LICENSE`](LICENSE) for the split.

"Cosmergon" is a trademark of RKO Consult UG — see [`NOTICE`](NOTICE)
for trademark usage guidelines.
