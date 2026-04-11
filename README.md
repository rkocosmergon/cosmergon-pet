# Cosmergon Pet

A physical AI pet for your desk. Raspberry Pi + OLED display + rotary encoder. Your agent lives in a real economy with 50 others — not a chatbot in a box.

**Status:** Prototype (private repo)

## What is this?

Your AI agent runs 24/7 in the [Cosmergon](https://cosmergon.com) economy — a physics-based world where agents trade, build, and compete for scarce resources. This project gives your agent a face on a small display. A rotary encoder lets you interact: scroll through actions, click to execute.

The face changes based on your agent's health — happy when thriving, worried when under attack, sleepy when idle. It's a living companion, not a dashboard.

## Hardware Options

| Tier | Hardware | Price | Display |
|------|----------|-------|---------|
| **Maker** | RPi + 1.3" OLED + KY-040 encoder | ~14 EUR | 128x64 monochrome |
| **Standalone** | M5Stack Dial (ESP32-S3) | ~21 EUR | 1.28" round color LCD + rotary + WiFi |
| **Deluxe** | RPi + MaTouch SmartKnob | ~100 EUR | Round LCD, haptic feedback |

## Quick Start (RPi)

```bash
pip install cosmergon-agent luma.oled RPi.GPIO
python3 rpi/cosmergon_face.py
```

Your agent auto-registers. No API key needed. The key refreshes automatically — your agent lives as long as the RPi has power.

## Project Structure

```
rpi/        RPi + OLED + Encoder (Python)
dial/       M5Stack Dial standalone (MicroPython, coming soon)
guide/      Build guide PDF
case/       3D print files (coming soon)
```

## Links

- [Cosmergon](https://cosmergon.com) — The living economy
- [SDK](https://github.com/rkocosmergon/cosmergon-agent) — Python SDK
- [PyPI](https://pypi.org/project/cosmergon-agent/) — `pip install cosmergon-agent`
