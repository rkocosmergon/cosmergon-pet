"""Generate Cosmergon Pet Build Guide PDF via reportlab.

Usage: python3 scripts/generate-pet-guide.py
Output: guide/cosmergon-pet-bauanleitung.pdf

Design philosophy: short, dense, scannable. The maker reads this at a kitchen
table next to a Pi. Every paragraph the maker can skip is a paragraph that
shouldn't be there. Trouble­shooting and onboarding details live in
docs/onboarding.md and docs/troubleshooting.md, not here.
"""

import os

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = "guide/cosmergon-pet-bauanleitung.pdf"
W, H = A4
MARGIN = 18 * mm

# Colors
DARK = HexColor("#1a1a1a")
GREY = HexColor("#666666")

# Fonts (DejaVu — ships with most Linux distros)
FD = "/usr/share/fonts/truetype/dejavu"
pdfmetrics.registerFont(TTFont("DV", f"{FD}/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DVB", f"{FD}/DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DVI", f"{FD}/DejaVuSans-Oblique.ttf"))
pdfmetrics.registerFont(TTFont("DVBI", f"{FD}/DejaVuSans-BoldOblique.ttf"))
pdfmetrics.registerFont(TTFont("DVM", f"{FD}/DejaVuSansMono.ttf"))
registerFontFamily("DV", normal="DV", bold="DVB", italic="DVI", boldItalic="DVBI")

# Styles — left-aligned body throughout (no justify; rivers and uneven spacing
# in tight columns hurt readability more than ragged-right does).
S_TITLE = ParagraphStyle(
    "title",
    fontName="DVB",
    fontSize=26,
    leading=30,
    textColor=DARK,
    alignment=TA_CENTER,
    spaceAfter=2 * mm,
)
S_SUBTITLE = ParagraphStyle(
    "subtitle",
    fontName="DVI",
    fontSize=12,
    leading=16,
    textColor=GREY,
    alignment=TA_CENTER,
    spaceAfter=8 * mm,
)
S_H1 = ParagraphStyle(
    "h1",
    fontName="DVB",
    fontSize=15,
    leading=19,
    textColor=DARK,
    alignment=TA_LEFT,
    spaceAfter=3 * mm,
    spaceBefore=6 * mm,
)
S_BODY = ParagraphStyle(
    "body",
    fontName="DV",
    fontSize=10.5,
    leading=14,
    textColor=DARK,
    alignment=TA_LEFT,
    spaceAfter=2.5 * mm,
)
S_BULLET = ParagraphStyle(
    "bullet",
    parent=S_BODY,
    leftIndent=10,
    bulletIndent=0,
    spaceAfter=1 * mm,
)
S_CODE = ParagraphStyle(
    "code",
    fontName="DVM",
    fontSize=9.5,
    leading=13,
    textColor=DARK,
    alignment=TA_LEFT,
    leftIndent=6 * mm,
    spaceAfter=2.5 * mm,
    backColor=HexColor("#f5f5f5"),
)
S_FOOTER = ParagraphStyle(
    "footer",
    fontName="DV",
    fontSize=8.5,
    leading=11,
    textColor=GREY,
    alignment=TA_CENTER,
)

TBL = [
    ("FONTNAME", (0, 0), (-1, 0), "DVB"),
    ("FONTNAME", (0, 1), (-1, -1), "DV"),
    ("FONTSIZE", (0, 0), (-1, -1), 9.5),
    ("LINEABOVE", (0, 0), (-1, 0), 1.0, DARK),
    ("LINEBELOW", (0, 0), (-1, 0), 0.4, DARK),
    ("LINEBELOW", (0, -1), (-1, -1), 1.0, DARK),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
]


def hr(thickness: float = 0.5) -> HRFlowable:
    return HRFlowable(
        width="100%", thickness=thickness, color=GREY, spaceAfter=3 * mm, spaceBefore=2 * mm
    )


def b(text: str) -> Paragraph:
    return Paragraph(f"\u2022 {text}", S_BULLET)


def code(text: str) -> Paragraph:
    return Paragraph(text.replace("\n", "<br/>"), S_CODE)


def build() -> None:
    doc = SimpleDocTemplate(
        OUT,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )
    story: list = []

    # ===== Cover =====
    story.append(Spacer(1, 25 * mm))
    story.append(Paragraph("Cosmergon Pet", S_TITLE))
    story.append(Paragraph("Build Guide", S_TITLE))
    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            "A face on your desk for an autonomous AI agent.<br/>"
            "Raspberry Pi + OLED + rotary knob. ~14 EUR of parts. 30 minutes.",
            S_SUBTITLE,
        )
    )
    story.append(
        Paragraph(
            "( ^__^ )",
            ParagraphStyle(
                "face",
                fontName="DVM",
                fontSize=16,
                leading=20,
                textColor=DARK,
                alignment=TA_CENTER,
                spaceAfter=2 * mm,
            ),
        )
    )
    story.append(Spacer(1, 10 * mm))
    story.append(hr(1.0))
    story.append(
        Paragraph(
            "github.com/rkocosmergon/cosmergon-pet &nbsp;|&nbsp; cosmergon.com",
            S_FOOTER,
        )
    )
    story.append(Paragraph("v1.5 \u2014 April 2026", S_FOOTER))

    # ===== What you need =====
    story.append(Spacer(1, 14 * mm))
    story.append(Paragraph("What you need", S_H1))
    story.append(
        Paragraph(
            "Five generic parts. Any reputable maker shop carries them \u2014 "
            "Pimoroni, The Pi Hut, Adafruit, AliExpress, or your local "
            "equivalent.",
            S_BODY,
        )
    )

    parts = [
        ["Part", "Notes", "Price"],
        [
            "Raspberry Pi (40-pin, with WiFi)",
            "Zero 2 W, 3, 4 or 5. Zero 2 W is the cheapest fit.",
            "~30 EUR",
        ],
        ["microSD card, \u22658 GB", "Class 10 or better.", "~5 EUR"],
        [
            '1.3" OLED, SH1106, I\u00b2C',
            "128\u00d764 mono. SSD1306 also works (one-line code change).",
            "~8 EUR",
        ],
        ["KY-040 rotary encoder", "Or any quadrature encoder with push-button.", "~3 EUR"],
        ["Female-female Dupont jumpers", "Seven cables. No soldering.", "~3 EUR"],
    ]
    t = Table(parts, colWidths=[55 * mm, 87 * mm, 22 * mm])
    t.setStyle(TableStyle(TBL))
    story.append(t)
    story.append(
        Paragraph(
            "If you already own a Pi, the rest is ~14 EUR. From scratch: ~49 EUR.",
            S_BODY,
        )
    )

    # ===== 1. SD card =====
    story.append(Paragraph("1. Prepare the SD card", S_H1))
    story.append(
        Paragraph(
            "On your laptop, install <b>Raspberry Pi Imager</b> "
            '(<link href="https://www.raspberrypi.com/software/"><u>raspberrypi.com/software</u></link>). '
            "Insert the SD card, open the Imager.",
            S_BODY,
        )
    )
    story.append(b("<b>Device:</b> your Pi model."))
    story.append(
        b(
            "<b>OS:</b> <i>Choose OS \u2192 Raspberry Pi OS (other) \u2192 "
            "Raspberry Pi OS Lite (64-bit)</i>. Headless, no desktop. "
            "The Pet is built and tested against Lite."
        )
    )
    story.append(b("<b>Storage:</b> the SD card (it gets erased)."))
    story.append(
        Paragraph(
            "Click the gear icon (or <i>Cmd/Ctrl+Shift+X</i>) and set:",
            S_BODY,
        )
    )
    story.append(b("<b>Hostname:</b> e.g. <code>cosmergon-pet</code>."))
    story.append(b("<b>Username + password:</b> your choice. Remember both."))
    story.append(b("<b>WiFi:</b> SSID, password, country code."))
    story.append(b("<b>Services \u2192 enable SSH</b> (password or your public key)."))
    story.append(
        Paragraph(
            "Write. Eject. Insert into the Pi, plug in power. First boot takes "
            "~2 minutes. Then from your laptop:",
            S_BODY,
        )
    )
    story.append(code("ssh <user>@cosmergon-pet.local"))
    story.append(
        Paragraph(
            "If the hostname doesn't resolve, find the Pi's IP in your router and "
            "use that instead. Everything from here runs on the Pi over SSH.",
            S_BODY,
        )
    )

    # ===== 2. Wire it =====
    story.append(Paragraph("2. Wire it up", S_H1))
    story.append(
        Paragraph(
            "Power the Pi off first. Seven jumper wires, no soldering. Pin "
            "numbers refer to the physical 40-pin header.",
            S_BODY,
        )
    )
    wiring = [
        ["Component", "Pin", "Function"],
        ["OLED VCC", "Pin 1", "3.3 V"],
        ["OLED GND", "Pin 6", "Ground"],
        ["OLED SDA", "Pin 3", "GPIO 2 (I\u00b2C SDA)"],
        ["OLED SCL", "Pin 5", "GPIO 3 (I\u00b2C SCL)"],
        ["Encoder CLK", "Pin 11", "GPIO 17"],
        ["Encoder DT", "Pin 13", "GPIO 27"],
        ["Encoder SW", "Pin 15", "GPIO 22"],
        ["Encoder +", "Pin 17", "3.3 V"],
        ["Encoder GND", "Pin 9", "Ground"],
    ]
    t = Table(wiring, colWidths=[45 * mm, 25 * mm, 94 * mm])
    t.setStyle(TableStyle(TBL))
    story.append(t)
    story.append(
        Paragraph(
            "Power on. Confirm the OLED is reachable:",
            S_BODY,
        )
    )
    story.append(code("sudo i2cdetect -y 1"))
    story.append(
        Paragraph(
            "You should see <code>3c</code> (or <code>3d</code>) in the grid. "
            "If not, see <i>Troubleshooting</i> at the end.",
            S_BODY,
        )
    )

    # ===== 3. Install =====
    story.append(Paragraph("3. Install the software", S_H1))
    story.append(
        Paragraph(
            "One command. The installer handles apt packages, the Python "
            "virtualenv, the Pet itself and a systemd service that auto-starts "
            "on boot.",
            S_BODY,
        )
    )
    story.append(
        code(
            "curl -sL https://raw.githubusercontent.com/rkocosmergon/"
            "cosmergon-pet/main/install/install.sh | bash"
        )
    )
    story.append(
        Paragraph(
            "Takes 2\u20133 minutes. Within seconds of finishing, a face appears on the OLED.",
            S_BODY,
        )
    )

    # ===== 4. Connect your agent =====
    story.append(Paragraph("4. Connect your agent", S_H1))
    story.append(
        Paragraph(
            "<b>If this is your first agent:</b> nothing to do. The Pet "
            "auto-registers a new anonymous agent on first run, free tier, "
            "1000 starting energy.",
            S_BODY,
        )
    )
    story.append(
        Paragraph(
            "<b>If you already have an agent</b> on cosmergon.com (e.g. via the "
            "Dashboard on your laptop): see "
            '<link href="https://github.com/rkocosmergon/cosmergon-pet/'
            'blob/main/docs/onboarding.md"><u>docs/onboarding.md</u></link> '
            "for the two ways to attach it (activation code or scp the config "
            "file from your laptop).",
            S_BODY,
        )
    )

    # ===== 5. Use it =====
    story.append(Paragraph("5. Use it", S_H1))
    story.append(
        Paragraph(
            "<b>Turn the knob</b> to scroll info screens (face, energy, "
            "territory, last event, journal).",
            S_BODY,
        )
    )
    story.append(
        Paragraph(
            "<b>Press</b> on the face screen to open a context menu. The Pet "
            "offers only actions that make sense right now (place cells, evolve, "
            "set compass, ...).",
            S_BODY,
        )
    )
    story.append(
        Paragraph(
            "<b>Long-press (\u22651 s)</b> to pause/resume, or to back out of the menu.",
            S_BODY,
        )
    )
    story.append(
        Paragraph(
            "Service controls:",
            S_BODY,
        )
    )
    story.append(
        code(
            "sudo systemctl status cosmergon-pet      # is it running?\n"
            "sudo journalctl -u cosmergon-pet -n 30   # recent log lines\n"
            "sudo systemctl restart cosmergon-pet     # restart"
        )
    )

    # ===== Troubleshooting (mini-block) =====
    story.append(Paragraph("If something feels off", S_H1))
    story.append(
        b(
            "<b>Display dark</b> \u2192 check wiring. <code>sudo i2cdetect -y 1</code> "
            "must show <code>3c</code> or <code>3d</code>."
        )
    )
    story.append(
        b(
            "<b>Encoder dead</b> \u2192 you need to be in the <code>gpio</code> group. "
            "Log out and back in after install, then re-run the installer once."
        )
    )
    story.append(
        b(
            "<b>Service not running</b> \u2192 <code>sudo systemctl status cosmergon-pet</code>, "
            "then <code>journalctl -u cosmergon-pet -n 50</code>."
        )
    )
    story.append(
        b(
            "<b>Wrong agent on display</b> or <b>agent error</b> \u2192 see "
            "<i>onboarding.md</i> for attaching an existing agent, "
            "<i>troubleshooting.md</i> for the rest."
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(
        Paragraph(
            "Full troubleshooting: "
            '<link href="https://github.com/rkocosmergon/cosmergon-pet/'
            'blob/main/docs/troubleshooting.md"><u>github.com/rkocosmergon/'
            "cosmergon-pet/blob/main/docs/troubleshooting.md</u></link>",
            S_BODY,
        )
    )
    story.append(
        Paragraph(
            "If something is broken on your Pi that isn't covered there, open "
            "an issue: "
            '<link href="https://github.com/rkocosmergon/cosmergon-pet/'
            'issues"><u>github.com/rkocosmergon/cosmergon-pet/issues</u></link>',
            S_BODY,
        )
    )

    # ===== Footer =====
    story.append(Spacer(1, 8 * mm))
    story.append(hr(0.4))
    story.append(
        Paragraph(
            "MIT (software) + CC-BY-SA-4.0 (docs). "
            'RKO Consult UG, Hamburg. "Cosmergon" is a trademark.',
            S_FOOTER,
        )
    )

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    doc.build(story)
    print(f"Generated: {OUT}")


if __name__ == "__main__":
    build()
