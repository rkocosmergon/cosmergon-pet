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
- **7 wires, no soldering** — everything plugs into the GPIO header
- **30 minutes** from blank SD card to a face on the display
- **No account needed for first start** — the agent auto-registers as
  anonymous (Free tier, rolling 24h session, 1000 energy) on first
  start. Existing users redeem an activation code with
  `cosmergon-agent activate COSM-…` before starting the Pet (build
  guide, Schritt 4)
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

## Hardware options

| Build | Parts | Price (EUR) | Notes |
|---|---|---|---|
| **Maker** | RPi (any 40-pin) + 1.3" OLED SH1106 I²C + KY-040 encoder | ~14 | If you already own a Pi. Software tested on Zero 2 W, 3, 4, 5. |
| **Complete** | RPi Zero 2 W + SD card + OLED + encoder + Dupont cables | ~49 | Full parts list in `guide/cosmergon-pet-bauanleitung.pdf`. |

## Project layout

```
src/cosmergon_pet/      The Pet software (Python)
install/                requirements + (later) install.sh, systemd
hardware/               Wiring tables, BOMs (markdown)
guide/                  Build guide (PDF)
docs/                   Getting started, troubleshooting, FAQ
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
