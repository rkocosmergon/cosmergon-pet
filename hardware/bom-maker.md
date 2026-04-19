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

## Regional direct links (EU / DACH)

If you're in Germany, Austria or Switzerland, these ship next-day and
save you international shipping:

| Part | Shop | Link |
|---|---|---|
| 1.3" OLED SH1106 I²C | Amazon.de (AZ-Delivery) | [B078J78R45](https://www.amazon.de/AZDelivery-Display-Arduino-Raspberry-Gratis/dp/B078J78R45) |
| 1.3" OLED SH1106 I²C | Voelkner | [12146484](https://www.voelkner.de/products/12146484/1.3-quot-128x64-OLED-Display-SH1106-IIC-I2C-Interface-einfarbig-blau.html) |
| KY-040 Encoder (3-pack) | Amazon.de (AZ-Delivery) | [B08247Q69J](https://www.amazon.de/AZDelivery-KY-040-Drehwinkelgeber-Parent/dp/B08247Q69J) |
| KY-040 Encoder | Voelkner | [12153902](https://www.voelkner.de/products/12153902/Drehregler-Rotary-Encoder-mit-Breakoutboard-ohne-Gewinde-und-Mutter.html) |
| Dupont F-F cables (40 pcs) | Amazon.de (AZ-Delivery) | [B07ZPD7PH8](https://www.amazon.de/AZDelivery-Jumper-Wire-Kabel-Parent/dp/B07ZPD7PH8) |
| Dupont F-F cables (40 pcs) | Voelkner | [12152443](https://www.voelkner.de/products/12152443/40pin-Jumper-Dupont-Kabel-Female-Female-trennbar-Laenge-0-50-m.html) |

PRs adding direct links for other regions are welcome.

## Compatibility

| Part | Substitutable with |
|---|---|
| SH1106 OLED | SSD1306 (change one import in `face.py`) |
| KY-040 encoder | Any quadrature encoder with push-switch (pin mapping in `wiring.md`) |
| Dupont F-F cables | Soldered wires if you prefer |

## See also

- [`wiring.md`](wiring.md) — pin-to-pin table for assembly
- [`../guide/cosmergon-pet-bauanleitung.pdf`](../guide/cosmergon-pet-bauanleitung.pdf) — full build guide
