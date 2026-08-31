# BOM — Maker build (~14 EUR)

You already own a 40-pin Raspberry Pi with WiFi. You only need the
OLED, encoder and cables.

## Parts

| Part | Qty | Price (EUR) | Notes |
|---|---|---|---|
| 1.3" OLED SH1106 I²C (128×64, mono) | 1 | ~8 | Any SH1106 I²C module. SSD1306 also works with a one-line code change — see issue template. |
| KY-040 Rotary Encoder (with push button) | 1 | ~3 | Typically sold as 3- or 5-pack — cheaper per piece, handy to have spares. |
| Female-to-Female Dupont cables | 7 | ~3 | Usually sold in packs of 40 or 120. |
| **Total** | | **~14** | |

These are commodity maker parts — any reputable electronics shop carries
them. Exact SKUs vary; the wiring table in [`wiring.md`](wiring.md)
works with any SH1106 I²C display and any quadrature encoder with
push-switch.

## Global maker shops (ship worldwide)

| Shop | Region | What they stock for this build |
|---|---|---|
| [Pimoroni](https://shop.pimoroni.com/) | UK / EU shipping | Own SH1106 breakouts, rotary encoders, Dupont jumpers |
| [The Pi Hut](https://thepihut.com/) | UK / worldwide | Large Pi-focused catalogue incl. Adafruit / SparkFun / Pimoroni |
| [Adafruit](https://www.adafruit.com/) | US | 128×64 OLEDs (their default is SSD1306 — needs one-line code change), rotary encoders, jumpers |
| [AliExpress](https://www.aliexpress.com/) | Global | Cheapest, slowest, quality varies — fine for commodity parts |

These are commodity parts — search any electronics retailer in your
region for the part names above. Per-part deep links go stale (prices
drift, stock runs out), so this guide deliberately doesn't carry them.

## Compatibility

| Part | Substitutable with |
|---|---|
| SH1106 OLED | SSD1306 (change one import in `face.py`) |
| KY-040 encoder | Any quadrature encoder with push-switch (pin mapping in `wiring.md`) |
| Dupont F-F cables | Soldered wires if you prefer |

## See also

- [`wiring.md`](wiring.md) — pin-to-pin table for assembly
- [`../guide/cosmergon-pet-bauanleitung.pdf`](../guide/cosmergon-pet-bauanleitung.pdf) — full build guide
