"""Generate hardware/wiring.svg — schematic wiring diagram for the Pet build.

Draws a simplified Raspberry Pi GPIO header + OLED + KY-040 encoder with
color-coded connection lines. Meant to be displayed by GitHub's SVG
renderer (not a precise Fritzing breadboard view, but a clear schematic).

Usage: python3 scripts/generate-wiring-svg.py
Output: hardware/wiring.svg
"""

from __future__ import annotations

OUT = "hardware/wiring.svg"

# Canvas
W, H = 900, 620
PAD = 20

# Palette (Cosmergon styleguide)
BG = "#0a0e1a"
TEXT = "#c8dcff"
ACCENT = "#00c8ff"
GRID = "rgba(0,200,255,0.15)"

# Wire colors (standard maker convention)
C_VCC = "#e74c3c"  # red — 3.3V
C_GND = "#2c3e50"  # dark — ground
C_DATA_OLED = "#3498db"  # blue — I2C SDA/SCL
C_DATA_ENC = "#2ecc71"  # green — encoder CLK/DT/SW


def header_pin_pos(pin: int) -> tuple[float, float]:
    """Return (x,y) of pin N on the 40-pin header block at top."""
    # Header block starts at x=330, y=40. Two rows, 20 cols.
    col = (pin - 1) // 2
    row = (pin - 1) % 2
    x = 330 + col * 12
    y = 60 + row * 16
    return x, y


def box(x: float, y: float, w: float, h: float, label: str, subtitle: str = "") -> str:
    """Draw a labeled component box."""
    s = (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
        f'rx="6" ry="6" fill="#111a2e" stroke="{ACCENT}" stroke-width="1.5"/>'
    )
    s += (
        f'<text x="{x + w / 2}" y="{y + 22}" fill="{TEXT}" '
        f'font-family="monospace" font-size="14" font-weight="bold" '
        f'text-anchor="middle">{label}</text>'
    )
    if subtitle:
        s += (
            f'<text x="{x + w / 2}" y="{y + 38}" fill="{TEXT}" '
            f'fill-opacity="0.6" font-family="monospace" font-size="10" '
            f'text-anchor="middle">{subtitle}</text>'
        )
    return s


def pin_label(x: float, y: float, text: str, anchor: str = "start") -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{TEXT}" '
        f'font-family="monospace" font-size="10" text-anchor="{anchor}">{text}</text>'
    )


def wire(x1: float, y1: float, x2: float, y2: float, color: str) -> str:
    # curved path — horizontal-then-vertical elbow in between
    mid = (y1 + y2) / 2
    return (
        f'<path d="M{x1},{y1} C{x1},{mid} {x2},{mid} {x2},{y2}" '
        f'stroke="{color}" stroke-width="2" fill="none"/>'
    )


def dot(x: float, y: float, color: str = ACCENT) -> str:
    return f'<circle cx="{x}" cy="{y}" r="3" fill="{color}"/>'


def build() -> None:
    parts: list[str] = []

    # SVG header
    parts.append(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}">'
    )
    parts.append(f'<rect width="{W}" height="{H}" fill="{BG}"/>')

    # Title
    parts.append(
        f'<text x="{W / 2}" y="30" fill="{TEXT}" font-family="monospace" '
        f'font-size="16" font-weight="bold" text-anchor="middle">'
        f"Cosmergon Pet — Wiring (Maker build)</text>"
    )

    # ==== Raspberry Pi 40-pin header (top) ====
    # Block outline
    parts.append(
        f'<rect x="320" y="50" width="250" height="48" rx="4" ry="4" '
        f'fill="#0b1322" stroke="{TEXT}" stroke-opacity="0.3" stroke-width="1"/>'
    )
    parts.append(
        f'<text x="445" y="120" fill="{TEXT}" fill-opacity="0.7" '
        f'font-family="monospace" font-size="11" text-anchor="middle">'
        f"Raspberry Pi — 40-pin GPIO header (any 40-pin RPi with WiFi)</text>"
    )

    # Highlight only the pins we use; draw all 40 as dots
    used = {
        1: ("3V3", C_VCC),
        3: ("SDA", C_DATA_OLED),
        5: ("SCL", C_DATA_OLED),
        6: ("GND", C_GND),
        9: ("GND", C_GND),
        11: ("GPIO17", C_DATA_ENC),
        13: ("GPIO27", C_DATA_ENC),
        15: ("GPIO22", C_DATA_ENC),
        17: ("3V3", C_VCC),
    }
    for pin in range(1, 41):
        x, y = header_pin_pos(pin)
        color = used.get(pin, (None, "rgba(200,220,255,0.25)"))[1]
        parts.append(dot(x, y, color))
        # Pin number — below for row 1, above for row 0
        txt_y = y + 14 if pin % 2 == 0 else y - 8
        if pin in used:
            parts.append(
                f'<text x="{x}" y="{txt_y}" fill="{TEXT}" '
                f'font-family="monospace" font-size="7" text-anchor="middle" '
                f'fill-opacity="0.85">{pin}</text>'
            )

    # ==== OLED (bottom left) ====
    oled_x, oled_y, oled_w, oled_h = 90, 380, 220, 150
    parts.append(box(oled_x, oled_y, oled_w, oled_h, 'OLED 1.3" SH1106', "I²C, 128×64 mono"))
    # OLED pins (left side of display body)
    oled_pins = [("VCC", C_VCC), ("GND", C_GND), ("SDA", C_DATA_OLED), ("SCL", C_DATA_OLED)]
    for i, (pname, pcolor) in enumerate(oled_pins):
        py = oled_y + 60 + i * 22
        parts.append(dot(oled_x, py, pcolor))
        parts.append(pin_label(oled_x - 8, py + 4, pname, anchor="end"))

    # ==== KY-040 Encoder (bottom right) ====
    enc_x, enc_y, enc_w, enc_h = 590, 380, 220, 150
    parts.append(box(enc_x, enc_y, enc_w, enc_h, "KY-040 Encoder", "rotary + push button"))
    # Encoder pins (right side of body)
    enc_pins = [
        ("CLK", C_DATA_ENC),
        ("DT", C_DATA_ENC),
        ("SW", C_DATA_ENC),
        ("+", C_VCC),
        ("GND", C_GND),
    ]
    for i, (pname, pcolor) in enumerate(enc_pins):
        py = enc_y + 45 + i * 18
        parts.append(dot(enc_x + enc_w, py, pcolor))
        parts.append(pin_label(enc_x + enc_w + 8, py + 4, pname))

    # ==== Wires ====
    # OLED → RPi
    def rpi_pin_port(pin: int) -> tuple[float, float]:
        x, y = header_pin_pos(pin)
        # Exit point = just below the row
        return x, (y + 3 if pin % 2 == 0 else y - 3)

    # OLED wire specs: (oled_pin_index, rpi_pin, color)
    oled_wires = [
        (0, 1, C_VCC),  # VCC  → pin 1 (3V3)
        (1, 6, C_GND),  # GND  → pin 6
        (2, 3, C_DATA_OLED),  # SDA → pin 3
        (3, 5, C_DATA_OLED),  # SCL → pin 5
    ]
    for idx, rpi_pin, color in oled_wires:
        py = oled_y + 60 + idx * 22
        rx, ry = rpi_pin_port(rpi_pin)
        parts.append(wire(oled_x, py, rx, ry, color))

    enc_wires = [
        (0, 11, C_DATA_ENC),  # CLK → pin 11
        (1, 13, C_DATA_ENC),  # DT  → pin 13
        (2, 15, C_DATA_ENC),  # SW  → pin 15
        (3, 17, C_VCC),  # +   → pin 17 (3V3)
        (4, 9, C_GND),  # GND → pin 9
    ]
    for idx, rpi_pin, color in enc_wires:
        py = enc_y + 45 + idx * 18
        rx, ry = rpi_pin_port(rpi_pin)
        parts.append(wire(enc_x + enc_w, py, rx, ry, color))

    # ==== Legend ====
    legend_x, legend_y = PAD + 10, H - 40
    legend = [
        (C_VCC, "3.3V (power)"),
        (C_GND, "GND"),
        (C_DATA_OLED, "I²C (SDA/SCL)"),
        (C_DATA_ENC, "GPIO (encoder)"),
    ]
    for i, (color, label) in enumerate(legend):
        lx = legend_x + i * 210
        parts.append(
            f'<line x1="{lx}" y1="{legend_y}" x2="{lx + 24}" y2="{legend_y}" stroke="{color}" stroke-width="3"/>'
        )
        parts.append(pin_label(lx + 30, legend_y + 4, label))

    # ==== Note ====
    parts.append(
        f'<text x="{W / 2}" y="{H - 10}" fill="{TEXT}" fill-opacity="0.5" '
        f'font-family="monospace" font-size="10" text-anchor="middle">'
        f"Schematic only — exact pin positions depend on RPi model. "
        f"See hardware/wiring.md for the full pinout table.</text>"
    )

    parts.append("</svg>")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print(f"SVG: {OUT}")


if __name__ == "__main__":
    build()
