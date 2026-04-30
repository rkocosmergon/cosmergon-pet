"""Generate hardware/images/social-preview.png (1280×640) for GitHub.

GitHub's social preview spec: 1280×640 PNG or JPG. This image appears
when someone shares github.com/rkocosmergon/cosmergon-pet on Hacker News,
Reddit, Slack, Mastodon, etc.

Usage: python3 scripts/generate-social-preview.py
Output: hardware/images/social-preview.png
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

OUT = "hardware/images/social-preview.png"

W, H = 1280, 640

# Cosmergon palette
BG = (10, 14, 26)  # #0a0e1a
TEXT = (200, 220, 255)  # #c8dcff
ACCENT = (0, 200, 255)  # #00c8ff
ACCENT2 = (255, 107, 53)  # #ff6b35
DIM = (130, 150, 180)

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
F_BOLD = f"{FONT_DIR}/DejaVuSansMono-Bold.ttf"
F_MONO = f"{FONT_DIR}/DejaVuSansMono.ttf"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def main() -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Thin accent border (top + bottom)
    draw.rectangle([(0, 0), (W, 4)], fill=ACCENT)
    draw.rectangle([(0, H - 4), (W, H)], fill=ACCENT)

    # Left column: ASCII faces column + label
    left_x = 90
    faces = [
        ("( ^__^ )", "thriving"),
        ("( -__- )", "content"),
        ("( ;__; )", "struggling"),
        ("( z__z )", "dormant"),
    ]
    face_y = 170
    face_font = font(F_BOLD, 44)
    mood_font = font(F_MONO, 20)
    for face_txt, mood in faces:
        draw.text((left_x, face_y), face_txt, fill=TEXT, font=face_font)
        draw.text((left_x + 8, face_y + 52), mood, fill=DIM, font=mood_font)
        face_y += 90

    # Right column: title + tagline + key info
    right_x = 560

    # Brand line
    draw.text(
        (right_x, 110),
        "// COSMERGON",
        fill=ACCENT2,
        font=font(F_MONO, 24),
    )

    # Title
    draw.text(
        (right_x, 150),
        "Cosmergon Pet",
        fill=TEXT,
        font=font(F_BOLD, 72),
    )

    # Tagline (two lines)
    tagline_font = font(F_MONO, 26)
    draw.text(
        (right_x, 250),
        "A physical AI agent companion",
        fill=TEXT,
        font=tagline_font,
    )
    draw.text(
        (right_x, 286),
        "for your desk.",
        fill=TEXT,
        font=tagline_font,
    )

    # Key info lines
    info_font = font(F_MONO, 22)
    info_y = 370
    for i, line in enumerate(
        [
            "Raspberry Pi + OLED + rotary encoder",
            "14-49 EUR  ·  9 wires, no soldering",
            "30 min from blank SD card to running Pet",
        ]
    ):
        draw.text((right_x, info_y + i * 34), line, fill=DIM, font=info_font)

    # Footer: URL + license
    footer_font = font(F_MONO, 18)
    draw.text(
        (right_x, H - 60),
        "github.com/rkocosmergon/cosmergon-pet",
        fill=ACCENT,
        font=footer_font,
    )
    draw.text(
        (right_x, H - 36),
        "MIT / CC-BY-SA-4.0  ·  RKO Consult UG",
        fill=DIM,
        font=font(F_MONO, 14),
    )

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"PNG: {OUT} ({os.path.getsize(OUT) // 1024} KB, {W}x{H})")


if __name__ == "__main__":
    main()
