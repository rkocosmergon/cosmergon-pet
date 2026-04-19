# BOM — Complete build (~49 EUR)

Everything from scratch. Recommended if you don't already own a Raspberry
Pi. Lowest-cost path to a working Pet.

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
KY-040-style encoder.

## Regional direct links (EU / DACH)

If you're in Germany, Austria or Switzerland, here are single-parcel
options:

### Voelkner (DE) — single parcel, ~38 EUR

| Part | Price (EUR) | Link |
|---|---|---|
| RPi Zero 2 W | 19.49 | [5171174](https://www.voelkner.de/products/5171174/Raspberry-Pi-Zero-2-W-Raspberry-Pi-Zero-2-W-512-MB-1-x-1.0-GHz.html) |
| 1.3" OLED SH1106 | 7.30 | [12146484](https://www.voelkner.de/products/12146484/1.3-quot-128x64-OLED-Display-SH1106-IIC-I2C-Interface-einfarbig-blau.html) |
| KY-040 Rotary Encoder | 1.53 | [12153902](https://www.voelkner.de/products/12153902/Drehregler-Rotary-Encoder-mit-Breakoutboard-ohne-Gewinde-und-Mutter.html) |
| Dupont F-F cables | 2.40 | [12152443](https://www.voelkner.de/products/12152443/40pin-Jumper-Dupont-Kabel-Female-Female-trennbar-Laenge-0-50-m.html) |
| microSD 16 GB | 7.09 | [6931473](https://www.voelkner.de/products/6931473/PNY-Micro-SD-Card-Elite-16-GB-HC-Komponenten-Speicher-Flash-Speicher.html) |

Note: Pi Zero 2 W availability at Voelkner fluctuates. Check stock
before ordering.

### Amazon.de — usually faster, mixed vendors

| Part | Price (EUR, ca.) | Link |
|---|---|---|
| RPi Zero 2 W | ~30 | [B09LH5SBPS](https://www.amazon.de/Raspberry-Pi-Zero-2-W/dp/B09LH5SBPS) |
| microSD 16 GB (SanDisk Ultra) | ~5 | [B010Q57SEE](https://www.amazon.de/dp/B010Q57SEE) |
| 1.3" OLED SH1106 I²C | ~8 | [B078J78R45](https://www.amazon.de/AZDelivery-Display-Arduino-Raspberry-Gratis/dp/B078J78R45) |
| KY-040 Rotary Encoder (3-pack) | ~3 | [B08247Q69J](https://www.amazon.de/AZDelivery-KY-040-Drehwinkelgeber-Parent/dp/B08247Q69J) |
| Dupont F-F cables (40 pcs) | ~3 | [B07ZPD7PH8](https://www.amazon.de/AZDelivery-Jumper-Wire-Kabel-Parent/dp/B07ZPD7PH8) |

## Software

- **Raspberry Pi OS Lite (64-bit)** — written via Raspberry Pi Imager.
  See the build guide.
- No extra purchases needed. The Pet software is MIT-licensed, free.

## See also

- [`wiring.md`](wiring.md) — pinouts
- [`../install/install.sh`](../install/install.sh) — one-line installer for after first boot
- [`../guide/cosmergon-pet-bauanleitung.pdf`](../guide/cosmergon-pet-bauanleitung.pdf) — full build guide
