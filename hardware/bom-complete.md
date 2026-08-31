# BOM — Complete build (~49 EUR)

Everything from scratch. Recommended if you don't already own a Raspberry
Pi. Lowest-cost path to a working Pet.

This parts list is **exemplary**: these are commodity maker parts, prices
and stock shift with the market. Buy equivalents wherever convenient —
the wiring in [`wiring.md`](wiring.md) works with any SH1106 I²C display
and any KY-040-style encoder.

## Parts

| Part | Qty | Price (EUR) | Notes |
|---|---|---|---|
| Raspberry Pi Zero 2 W | 1 | ~30 | Smallest, cheapest 40-pin Pi with WiFi. Any other 40-pin Pi with WiFi works too. |
| microSD card, ≥ 16 GB, class 10 or better | 1 | ~5 | SanDisk Ultra is a reliable default. |
| 1.3" OLED SH1106 I²C (128×64) | 1 | ~8 | See [`bom-maker.md`](bom-maker.md) for alternatives. |
| KY-040 Rotary Encoder | 1 | ~3 | — |
| Female-to-Female Dupont cables | 7 | ~3 | Packs of 40 or 120. |
| **Total** | | **~49** | |

## Power supply

Not in the BOM above — you probably have a micro-USB or USB-C charger
lying around. If not:

- RPi Zero 2 W: 5 V / 2.5 A micro-USB
- RPi 3 / 3B+: 5 V / 2.5 A micro-USB
- RPi 4: 5 V / 3 A USB-C
- RPi 5: 5 V / 5 A USB-C (official PSU recommended)

## Global maker shops (ship worldwide)

| Shop | Region | Pi Zero 2 W | OLED / Encoder / Cables |
|---|---|---|---|
| [Pimoroni](https://shop.pimoroni.com/) | UK / EU | Yes (stock varies) | Own breakouts available |
| [The Pi Hut](https://thepihut.com/) | UK / worldwide | Yes | Large catalogue incl. Adafruit / SparkFun / Pimoroni |
| [Adafruit](https://www.adafruit.com/) | US | Yes | 128×64 OLEDs (default SSD1306; SH1106 modules available separately), encoders, jumpers |
| [AliExpress](https://www.aliexpress.com/) | Global | Clone / CM variants | Cheapest for the small parts |

These are commodity maker parts — SKUs vary by shop. The wiring table
in [`wiring.md`](wiring.md) works with any SH1106 I²C display and any
KY-040-style encoder. Search any electronics retailer in your region
for the part names above; per-part deep links go stale (prices drift,
stock runs out), so this guide deliberately doesn't carry them.

## Software

- **Raspberry Pi OS Lite (64-bit)** — written via Raspberry Pi Imager.
  See the build guide.
- No extra purchases needed. The Pet software is MIT-licensed, free.

## See also

- [`wiring.md`](wiring.md) — pinouts
- [`../install/install.sh`](../install/install.sh) — one-line installer for after first boot
- [`../guide/cosmergon-pet-bauanleitung.pdf`](../guide/cosmergon-pet-bauanleitung.pdf) — full build guide
