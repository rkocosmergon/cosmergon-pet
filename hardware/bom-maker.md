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

## Suggested shops

### Amazon.de (single-parcel, often next-day)

| Part | Link |
|---|---|
| 1.3" OLED SH1106 I²C | [AZ-Delivery 1.3" OLED](https://www.amazon.de/AZDelivery-Display-Arduino-Raspberry-Gratis/dp/B078J78R45) |
| KY-040 Encoder (3-pack) | [AZ-Delivery KY-040](https://www.amazon.de/AZDelivery-KY-040-Drehwinkelgeber-Parent/dp/B08247Q69J) |
| Dupont F-F cables (40 pcs) | [AZ-Delivery Jumper Wire F-F](https://www.amazon.de/AZDelivery-Jumper-Wire-Kabel-Parent/dp/B07ZPD7PH8) |

### Völkner (DE, often cheaper on individual parts)

| Part | Link |
|---|---|
| 1.3" OLED SH1106 I²C | [voelkner.de/12146484](https://www.voelkner.de/products/12146484/1.3-quot-128x64-OLED-Display-SH1106-IIC-I2C-Interface-einfarbig-blau.html) |
| KY-040 Encoder | [voelkner.de/12153902](https://www.voelkner.de/products/12153902/Drehregler-Rotary-Encoder-mit-Breakoutboard-ohne-Gewinde-und-Mutter.html) |
| Dupont F-F cables (40 pcs) | [voelkner.de/12152443](https://www.voelkner.de/products/12152443/40pin-Jumper-Dupont-Kabel-Female-Female-trennbar-Laenge-0-50-m.html) |

### Outside DE/AT/CH

- **The Pi Hut**, **Pimoroni** (UK / worldwide)
- **Adafruit** (US — their 128×64 OLED is SSD1306-based, needs the SSD1306 code change)
- **AliExpress** — cheapest, slowest, quality varies

PRs with links for your region are welcome.

## Compatibility matrix

| Part | Substitutable with |
|---|---|
| SH1106 OLED | SSD1306 (change one import in `face.py`) |
| KY-040 encoder | Any quadrature encoder with push-switch (pin mapping in `wiring.md`) |
| Dupont F-F cables | Soldered wires if you prefer |

## See also

- [`wiring.md`](wiring.md) — pin-to-pin table for assembly
- [`../guide/cosmergon-pet-bauanleitung.pdf`](../guide/cosmergon-pet-bauanleitung.pdf) — full build guide
