# Hardware

Three build variants. Same Pet software, different parts depending on what
you own and how much you want to spend.

| Build | Price (EUR) | When it fits | BOM |
|---|---|---|---|
| **Maker** | ~14 | You already own a 40-pin Raspberry Pi | [`bom-maker.md`](bom-maker.md) |
| **Complete** | ~49 | Nothing on the shelf — buy everything | [`bom-complete.md`](bom-complete.md) |

Wiring (both builds share the same hardware — RPi + OLED + KY-040 encoder):
[`wiring.md`](wiring.md) and [`wiring.svg`](wiring.svg).

## Which RPi model?

Any 40-pin Raspberry Pi with WiFi works: **Zero 2 W, 3, 3A+, 3B, 3B+, 4, 5**.

The Pet uses almost no CPU or memory. The Zero 2 W is the cheapest option
and the one recommended in the build guide. A Pi 5 is overkill — save it for
something else.

## Why not an RPi Pico / ESP32?

The Pet depends on `cosmergon-agent` (Python SDK) and makes HTTP(S) requests
over WiFi. That's Linux territory — the RPi Zero 2 W (~30 EUR, smallest
40-pin Pi with WiFi) is the cheapest entry point. RP2040 / ESP32 ports
would need a separate implementation (different HTTPS stack, different
display libraries); none exists in this repo.

## Shops and prices

Prices in the BOMs are orientation values from **April 2026**, based on the
shops linked per line (mostly Amazon.de and Völkner.de for DE/AT/CH).
Verify before ordering — component prices drift, shops go out of stock.

For non-EU buyers: the same parts are widely available on AliExpress,
Mouser, DigiKey, Adafruit, The Pi Hut, etc. PRs to add more shops are
welcome.
