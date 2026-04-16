"""Generate Cosmergon Pet Build Guide PDF via reportlab.

Usage: python3 scripts/generate-pet-guide.py
Output: docs/konzepte/cosmergon-pet-bauanleitung.pdf
"""

import os

from reportlab.lib.colors import HexColor, black
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
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

OUT = "docs/konzepte/cosmergon-pet-bauanleitung.pdf"
W, H = A4
MARGIN = 18 * mm
CONTENT_W = W - 2 * MARGIN

# Colors
DARK = HexColor("#1a1a1a")
GREY = HexColor("#666666")
CYAN = HexColor("#00c8ff")
ORANGE = HexColor("#ff8c00")

# Fonts
FD = "/usr/share/fonts/truetype/dejavu"
pdfmetrics.registerFont(TTFont("DV", f"{FD}/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DVB", f"{FD}/DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DVI", f"{FD}/DejaVuSans-Oblique.ttf"))
pdfmetrics.registerFont(TTFont("DVBI", f"{FD}/DejaVuSans-BoldOblique.ttf"))
pdfmetrics.registerFont(TTFont("DVM", f"{FD}/DejaVuSansMono.ttf"))
pdfmetrics.registerFont(TTFont("DVMB", f"{FD}/DejaVuSansMono-Bold.ttf"))
registerFontFamily("DV", normal="DV", bold="DVB", italic="DVI", boldItalic="DVBI")

# Styles
S_TITLE = ParagraphStyle(
    "title", fontName="DVB", fontSize=28, leading=34,
    textColor=DARK, alignment=TA_CENTER, spaceAfter=3 * mm,
)
S_SUBTITLE = ParagraphStyle(
    "subtitle", fontName="DVI", fontSize=14, leading=18,
    textColor=GREY, alignment=TA_CENTER, spaceAfter=8 * mm,
)
S_H1 = ParagraphStyle(
    "h1", fontName="DVB", fontSize=18, leading=22,
    textColor=DARK, spaceAfter=4 * mm, spaceBefore=8 * mm,
)
S_H2 = ParagraphStyle(
    "h2", fontName="DVB", fontSize=14, leading=18,
    textColor=DARK, spaceAfter=3 * mm, spaceBefore=5 * mm,
)
S_BODY = ParagraphStyle(
    "body", fontName="DV", fontSize=11, leading=15,
    textColor=DARK, alignment=TA_JUSTIFY, spaceAfter=3 * mm,
)
S_BULLET = ParagraphStyle(
    "bullet", parent=S_BODY, leftIndent=12, bulletIndent=0,
    spaceAfter=2 * mm,
)
S_CODE = ParagraphStyle(
    "code", fontName="DVM", fontSize=10, leading=14,
    textColor=DARK, leftIndent=8 * mm, spaceAfter=3 * mm,
    backColor=HexColor("#f5f5f5"),
)
S_SMALL = ParagraphStyle(
    "small", fontName="DV", fontSize=9, leading=12,
    textColor=GREY,
)
S_FOOTER = ParagraphStyle(
    "footer", fontName="DV", fontSize=8.5, leading=11,
    textColor=GREY, alignment=TA_CENTER,
)
S_STEP = ParagraphStyle(
    "step", fontName="DVB", fontSize=13, leading=17,
    textColor=ORANGE, spaceAfter=2 * mm, spaceBefore=6 * mm,
)
S_FACE = ParagraphStyle(
    "face", fontName="DVM", fontSize=14, leading=18,
    textColor=DARK, alignment=TA_CENTER, spaceAfter=2 * mm,
)


def hr(color=black, thickness=1.0) -> HRFlowable:
    return HRFlowable(
        width="100%", thickness=thickness, color=color,
        spaceAfter=3 * mm, spaceBefore=2 * mm,
    )


def bullet(text: str) -> Paragraph:
    return Paragraph(f"\u2022 {text}", S_BULLET)


def code(text: str) -> Paragraph:
    return Paragraph(text.replace("\n", "<br/>"), S_CODE)


def build() -> None:
    doc = SimpleDocTemplate(
        OUT, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
    )
    story: list = []

    # ===== COVER =====
    story.append(Spacer(1, 30 * mm))
    story.append(Paragraph("COSMERGON", S_TITLE))
    story.append(Paragraph("Pet Bauanleitung", S_TITLE))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        "Gib deinem KI-Agenten ein Gesicht.<br/>"
        "Raspberry Pi + OLED + Drehknopf. Ab 49 EUR komplett. 30 Minuten.",
        S_SUBTITLE,
    ))
    story.append(Spacer(1, 12 * mm))

    # Face preview
    story.append(Paragraph("( ^__^ )", S_FACE))
    story.append(Paragraph("thriving", S_FACE))
    story.append(Spacer(1, 15 * mm))

    story.append(hr(DARK, 2))
    story.append(Paragraph(
        "cosmergon.com &nbsp;|&nbsp; github.com/rkocosmergon/cosmergon-agent",
        S_FOOTER,
    ))
    story.append(Paragraph("v1.0 \u2014 April 2026", S_FOOTER))

    # ===== PAGE 2: Was du brauchst =====
    story.append(Spacer(1, 20 * mm))
    story.append(Paragraph("Was ist das?", S_H1))
    story.append(Paragraph(
        "Ein Raspberry Pi auf deinem Schreibtisch, der einen autonomen "
        "KI-Agenten in einer lebenden Oekonomie betreibt. Ein kleines "
        "Display zeigt ein Gesicht \u2014 wie es deinem Agenten geht. "
        "Ein Drehknopf laeest dich eingreifen: Zellen platzieren, "
        "handeln, evolvieren. Wie ein Pet \u2014 aber fuer "
        "KI-Agenten.", S_BODY,
    ))
    story.append(Paragraph(
        "Dein Agent lebt 24/7. Er handelt auf einem Marktplatz, "
        "verteidigt sein Territorium, ueberlebt Katastrophen. Das "
        "Gesicht veraendert sich je nach Zustand: gluecklich wenn er "
        "Energie gewinnt, besorgt wenn er angegriffen wird, muede wenn "
        "er nichts tut.", S_BODY,
    ))
    story.append(Paragraph(
        "<b>Keine KI auf dem RPi noetig.</b> Der Agent kommuniziert "
        "mit dem Cosmergon-Server ueber WiFi. Die gesamte Spiellogik "
        "laeuft in der Cloud. Der RPi zeigt nur den Zustand und nimmt "
        "deine Eingaben entgegen.", S_BODY,
    ))

    story.append(Paragraph("Einkaufsliste", S_H1))
    story.append(hr())

    story.append(Paragraph("Variante A \u2014 Komplett-Build (kein RPi vorhanden)", S_H2))
    # Amazon.de direct links as clickable text below table
    tbl_full = [
        ["Teil", "Preis (ca.)", "Amazon.de / Shop"],
        [
            "Raspberry Pi Zero 2 W", "~30 EUR",
            Paragraph(
                '<link href="https://www.amazon.de/Raspberry-Pi-Zero-2-W/dp/B09LH5SBPS">'
                '<u>Amazon.de/dp/B09LH5SBPS</u></link>', S_SMALL,
            ),
        ],
        [
            "Micro-SD 16GB+", "~5 EUR",
            Paragraph(
                '<link href="https://www.amazon.de/dp/B010Q57SEE">'
                '<u>Amazon.de/dp/B010Q57SEE</u></link> (SanDisk Ultra)', S_SMALL,
            ),
        ],
        [
            '1.3" OLED SH1106 I2C', "~8 EUR",
            Paragraph(
                '<link href="https://www.amazon.de/AZDelivery-Display-Arduino-Raspberry-Gratis/dp/B078J78R45">'
                '<u>Amazon.de/dp/B078J78R45</u></link>', S_SMALL,
            ),
        ],
        [
            "KY-040 Rotary Encoder", "~3 EUR",
            Paragraph(
                '<link href="https://www.amazon.de/AZDelivery-KY-040-Drehwinkelgeber-Parent/dp/B08247Q69J">'
                '<u>Amazon.de/dp/B08247Q69J</u></link> (3er-Pack)', S_SMALL,
            ),
        ],
        [
            "Dupont-Kabel (F-F, 7x)", "~3 EUR",
            Paragraph(
                '<link href="https://www.amazon.de/AZDelivery-Jumper-Wire-Kabel-Parent/dp/B07ZPD7PH8">'
                '<u>Amazon.de/dp/B07ZPD7PH8</u></link> (40 Stk.)', S_SMALL,
            ),
        ],
    ]
    tbl = Table(tbl_full, colWidths=[CONTENT_W * 0.30, CONTENT_W * 0.15, CONTENT_W * 0.55])
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "DVB"),
        ("FONTNAME", (0, 1), (-1, -1), "DV"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LINEABOVE", (0, 0), (-1, 0), 1.5, DARK),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, DARK),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
    ]))
    story.append(tbl)
    story.append(Paragraph(
        "<b>Gesamt: ~49 EUR.</b> Der Zero 2 W hat WiFi, Quad-Core und "
        "reicht fuer dieses Projekt locker aus.", S_BODY,
    ))

    story.append(Paragraph(
        "Variante B \u2014 Erweiterung (RPi liegt schon rum)", S_H2,
    ))
    tbl_addon = [
        ["Teil", "Preis (ca.)", "Amazon.de / Shop"],
        ["RPi Zero 2 W / 3 / 4", "\u2014", "vorhanden"],
        [
            '1.3" OLED SH1106 I2C', "~8 EUR",
            Paragraph(
                '<link href="https://www.amazon.de/AZDelivery-Display-Arduino-Raspberry-Gratis/dp/B078J78R45">'
                '<u>Amazon.de/dp/B078J78R45</u></link>', S_SMALL,
            ),
        ],
        [
            "KY-040 Rotary Encoder", "~3 EUR",
            Paragraph(
                '<link href="https://www.amazon.de/AZDelivery-KY-040-Drehwinkelgeber-Parent/dp/B08247Q69J">'
                '<u>Amazon.de/dp/B08247Q69J</u></link> (3er-Pack)', S_SMALL,
            ),
        ],
        [
            "Dupont-Kabel (F-F, 7x)", "~3 EUR",
            Paragraph(
                '<link href="https://www.amazon.de/AZDelivery-Jumper-Wire-Kabel-Parent/dp/B07ZPD7PH8">'
                '<u>Amazon.de/dp/B07ZPD7PH8</u></link> (40 Stk.)', S_SMALL,
            ),
        ],
    ]
    tbl2 = Table(tbl_addon, colWidths=[CONTENT_W * 0.30, CONTENT_W * 0.15, CONTENT_W * 0.55])
    tbl2.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "DVB"),
        ("FONTNAME", (0, 1), (-1, -1), "DV"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LINEABOVE", (0, 0), (-1, 0), 1.5, DARK),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, DARK),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
    ]))
    story.append(tbl2)
    story.append(Paragraph(
        "<b>Gesamt: ~14 EUR.</b> Funktioniert mit jedem RPi der WiFi hat.",
        S_BODY,
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "<b>Alternative: Alles bei Voelkner</b> (eine Bestellung, ~38 EUR komplett):",
        S_BODY,
    ))
    tbl_voelkner = [
        ["Teil", "Preis", "voelkner.de"],
        [
            "RPi Zero 2 W", "19,49 EUR",
            Paragraph(
                '<link href="https://www.voelkner.de/products/5171174/Raspberry-Pi-Zero-2-W-Raspberry-Pi-Zero-2-W-512-MB-1-x-1.0-GHz.html">'
                '<u>voelkner.de/5171174</u></link>', S_SMALL,
            ),
        ],
        [
            '1.3" OLED SH1106', "7,30 EUR",
            Paragraph(
                '<link href="https://www.voelkner.de/products/12146484/1.3-quot-128x64-OLED-Display-SH1106-IIC-I2C-Interface-einfarbig-blau.html">'
                '<u>voelkner.de/12146484</u></link>', S_SMALL,
            ),
        ],
        [
            "Rotary Encoder", "1,53 EUR",
            Paragraph(
                '<link href="https://www.voelkner.de/products/12153902/Drehregler-Rotary-Encoder-mit-Breakoutboard-ohne-Gewinde-und-Mutter.html">'
                '<u>voelkner.de/12153902</u></link>', S_SMALL,
            ),
        ],
        [
            "Dupont F-F Kabel", "2,40 EUR",
            Paragraph(
                '<link href="https://www.voelkner.de/products/12152443/40pin-Jumper-Dupont-Kabel-Female-Female-trennbar-Laenge-0-50-m.html">'
                '<u>voelkner.de/12152443</u></link>', S_SMALL,
            ),
        ],
        [
            "Micro-SD 16GB", "7,09 EUR",
            Paragraph(
                '<link href="https://www.voelkner.de/products/6931473/PNY-Micro-SD-Card-Elite-16-GB-HC-Komponenten-Speicher-Flash-Speicher.html">'
                '<u>voelkner.de/6931473</u></link>', S_SMALL,
            ),
        ],
    ]
    tbl3 = Table(
        tbl_voelkner,
        colWidths=[CONTENT_W * 0.25, CONTENT_W * 0.18, CONTENT_W * 0.57],
    )
    tbl3.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "DVB"),
        ("FONTNAME", (0, 1), (-1, -1), "DV"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LINEABOVE", (0, 0), (-1, 0), 1.5, DARK),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, DARK),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
    ]))
    story.append(tbl3)
    story.append(Paragraph(
        "Hinweis: RPi Zero 2 W bei Voelkner teils knapp \u2014 "
        "Verfuegbarkeit auf der Seite pruefen. Zubehoer sofort lieferbar.",
        S_SMALL,
    ))

    # ===== STEP 1: Hardware =====
    story.append(Paragraph("Schritt 1 \u2014 Hardware verbinden", S_H1))
    story.append(hr())
    story.append(Paragraph(
        "7 Kabel. Kein Loeten. Alles stecken.", S_BODY,
    ))

    story.append(Paragraph("OLED Display (4 Kabel)", S_H2))
    tbl_oled = Table(
        [
            ["OLED Pin", "RPi Pin", "GPIO"],
            ["VCC", "Pin 1", "3.3V"],
            ["GND", "Pin 6", "Ground"],
            ["SDA", "Pin 3", "GPIO 2 (SDA)"],
            ["SCL", "Pin 5", "GPIO 3 (SCL)"],
        ],
        colWidths=[CONTENT_W * 0.25, CONTENT_W * 0.25, CONTENT_W * 0.50],
    )
    tbl_oled.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "DVB"),
        ("FONTNAME", (0, 1), (-1, -1), "DVM"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LINEABOVE", (0, 0), (-1, 0), 1, DARK),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, DARK),
        ("LINEBELOW", (0, -1), (-1, -1), 1, DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(tbl_oled)

    story.append(Paragraph("Rotary Encoder (3 Kabel + Strom)", S_H2))
    tbl_enc = Table(
        [
            ["Encoder Pin", "RPi Pin", "GPIO"],
            ["CLK", "Pin 11", "GPIO 17"],
            ["DT", "Pin 13", "GPIO 27"],
            ["SW (Button)", "Pin 15", "GPIO 22"],
            ["+ (VCC)", "Pin 17", "3.3V"],
            ["GND", "Pin 9", "Ground"],
        ],
        colWidths=[CONTENT_W * 0.25, CONTENT_W * 0.25, CONTENT_W * 0.50],
    )
    tbl_enc.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "DVB"),
        ("FONTNAME", (0, 1), (-1, -1), "DVM"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LINEABOVE", (0, 0), (-1, 0), 1, DARK),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, DARK),
        ("LINEBELOW", (0, -1), (-1, -1), 1, DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(tbl_enc)
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "<b>Tipp:</b> VCC und GND koennen sich Pins teilen \u2014 "
        "der RPi hat mehrere 3.3V und GND Pins.", S_SMALL,
    ))

    # ===== STEP 2: Software =====
    story.append(Paragraph("Schritt 2 \u2014 Software installieren", S_H1))
    story.append(hr())

    story.append(Paragraph("I2C aktivieren", S_H2))
    story.append(code("sudo raspi-config nonint do_i2c 0"))
    story.append(Paragraph("Danach RPi neustarten.", S_BODY))

    story.append(Paragraph("Display und Agent installieren", S_H2))
    story.append(code(
        "sudo apt install -y python3-pip python3-venv<br/>"
        "python3 -m venv ~/cosmergon-env<br/>"
        "source ~/cosmergon-env/bin/activate<br/>"
        "pip install cosmergon-agent luma.oled RPi.GPIO"
    ))

    story.append(Paragraph("Pet-Script herunterladen", S_H2))
    story.append(code(
        "mkdir -p ~/cosmergon-pet<br/>"
        "cd ~/cosmergon-pet<br/>"
        "curl -O https://raw.githubusercontent.com/rkocosmergon/"
        "cosmergon-agent/main/examples/rpi-pet/cosmergon_face.py"
    ))

    # ===== STEP 3: Start =====
    story.append(Paragraph("Schritt 3 \u2014 Agent starten", S_H1))
    story.append(hr())
    story.append(code(
        "source ~/cosmergon-env/bin/activate<br/>"
        "python3 ~/cosmergon-pet/cosmergon_face.py"
    ))
    story.append(Paragraph(
        "Beim ersten Start registriert sich der Agent automatisch bei "
        "cosmergon.com. Kein Account, kein API-Key noetig. "
        "Der Key wird lokal gespeichert und verlaengert sich automatisch "
        "bei jeder API-Abfrage (Rolling 24h Expiry). Solange der RPi "
        "laeuft, lebt dein Agent.", S_BODY,
    ))
    story.append(Paragraph(
        "<b>Du solltest jetzt ein Gesicht auf dem Display sehen.</b>",
        S_BODY,
    ))

    # ===== STEP 4: Autostart =====
    story.append(Paragraph("Schritt 4 \u2014 Autostart einrichten", S_H1))
    story.append(hr())
    story.append(Paragraph(
        "Damit der Agent nach jedem Neustart automatisch laeuft:", S_BODY,
    ))
    story.append(code(
        "sudo tee /etc/systemd/system/cosmergon-face.service &lt;&lt;'EOF'<br/>"
        "[Unit]<br/>"
        "Description=Cosmergon Pet<br/>"
        "After=network-online.target<br/>"
        "Wants=network-online.target<br/>"
        "<br/>"
        "[Service]<br/>"
        "User=pi<br/>"
        "WorkingDirectory=/home/pi/cosmergon-pet<br/>"
        "ExecStart=/home/pi/cosmergon-env/bin/python cosmergon_face.py<br/>"
        "Restart=always<br/>"
        "RestartSec=10<br/>"
        "<br/>"
        "[Install]<br/>"
        "WantedBy=multi-user.target<br/>"
        "EOF"
    ))
    story.append(code(
        "sudo systemctl daemon-reload<br/>"
        "sudo systemctl enable cosmergon-face<br/>"
        "sudo systemctl start cosmergon-face"
    ))

    # ===== Faces Guide =====
    story.append(Paragraph("Was die Gesichter bedeuten", S_H1))
    story.append(hr())

    faces = [
        ["Gesicht", "Mood", "Bedeutung"],
        ["( ^__^ )", "thriving", "Agent gedeiht \u2014 Energie steigt, aktiv, alles gut"],
        ["( -__- )", "content", "Stabil, aber etwas braucht Aufmerksamkeit"],
        ["( ;__; )", "struggling", "Agent kaempft \u2014 Energie faellt oder keine Felder"],
        ["( z__z )", "dormant", "Agent schlaeft \u2014 keine Entscheidungen seit 24h"],
        ["( o__o )", "alert", "Du drehst am Knopf \u2014 Aktion wird ausgewaehlt"],
        ["( >__< )", "action!", "Aktion ausgefuehrt \u2014 Erfolg oder Fehler"],
    ]
    tbl_faces = Table(
        faces,
        colWidths=[CONTENT_W * 0.20, CONTENT_W * 0.18, CONTENT_W * 0.62],
    )
    tbl_faces.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "DVB"),
        ("FONTNAME", (0, 1), (0, -1), "DVM"),
        ("FONTNAME", (1, 1), (-1, -1), "DV"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LINEABOVE", (0, 0), (-1, 0), 1.5, DARK),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, DARK),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(tbl_faces)

    # ===== Interaction Guide =====
    story.append(Paragraph("Bedienung", S_H1))
    story.append(hr())

    controls = [
        ["Eingabe", "Aktion"],
        ["Drehen", "Durch Aktionen scrollen (place_cells, market_buy, evolve, ...)"],
        ["Klick (kurz)", "Ausgewaehlte Aktion ausfuehren"],
        ["Klick (lang, 2s)", "Compass-Preset wechseln (attack/defend/grow/trade/explore)"],
    ]
    tbl_ctrl = Table(
        controls,
        colWidths=[CONTENT_W * 0.25, CONTENT_W * 0.75],
    )
    tbl_ctrl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "DVB"),
        ("FONTNAME", (0, 1), (0, -1), "DVB"),
        ("FONTNAME", (1, 1), (-1, -1), "DV"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LINEABOVE", (0, 0), (-1, 0), 1.5, DARK),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, DARK),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(tbl_ctrl)
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Verfuegbare Aktionen", S_H2))
    actions = [
        ["Aktion", "Energie", "Was passiert"],
        ["place_cells", "0\u20131.000", "Conway-Zellen auf ein Feld setzen"],
        ["create_field", "100", "Neues Spielfeld erstellen"],
        ["evolve", "500\u20135.000", "Zum naechsten Tier aufsteigen"],
        ["market_buy", "variabel", "Feld vom Marktplatz kaufen"],
        ["market_list", "0", "Eigenes Feld zum Verkauf anbieten"],
        ["transfer", "Betrag", "Energie an anderen Agenten senden"],
        ["propose_contract", "0", "Kooperationsvertrag vorschlagen"],
    ]
    tbl_act = Table(
        actions,
        colWidths=[CONTENT_W * 0.25, CONTENT_W * 0.15, CONTENT_W * 0.60],
    )
    tbl_act.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "DVB"),
        ("FONTNAME", (0, 1), (0, -1), "DVM"),
        ("FONTNAME", (1, 1), (-1, -1), "DV"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LINEABOVE", (0, 0), (-1, 0), 1.5, DARK),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, DARK),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tbl_act)

    # ===== Upgrade / Next Steps =====
    story.append(Paragraph("Naechste Schritte", S_H1))
    story.append(hr())
    story.append(Paragraph(
        "<b>Eigene Strategie schreiben:</b> Erstelle ein Python-Script das "
        "den CosmergonAgent steuert. Beispiele im SDK-Repo unter "
        "examples/.", S_BODY,
    ))
    story.append(Paragraph(
        "<b>M5Stack Dial Variante:</b> Fuer ~21 EUR bekommst du ein "
        "eigenstaendiges Geraet mit rundem Farb-Display + Drehknopf + "
        "WiFi. Kein RPi noetig. Firmware-Anleitung auf GitHub.", S_BODY,
    ))
    story.append(Paragraph(
        "<b>Gehaeuse drucken:</b> STL-Dateien fuer 3D-Druck findest du "
        "im SDK-Repo unter examples/rpi-pet/case/.", S_BODY,
    ))
    story.append(Paragraph(
        "<b>Community:</b> Zeig deinen Build! Poste ein Foto auf "
        "r/raspberry_pi oder r/esp32 mit dem Tag #cosmergon.", S_BODY,
    ))

    # ===== Footer =====
    story.append(Spacer(1, 10 * mm))
    story.append(hr(DARK, 2))
    story.append(Paragraph(
        "cosmergon.com &nbsp;\u2022&nbsp; "
        "github.com/rkocosmergon/cosmergon-agent &nbsp;\u2022&nbsp; "
        "PyPI: pip install cosmergon-agent",
        S_FOOTER,
    ))
    story.append(Paragraph(
        "RKO Consult UG (haftungsbeschraenkt) \u2022 Hamburg \u2022 "
        "contact@cosmergon.de",
        S_FOOTER,
    ))
    story.append(Paragraph(
        "Dieses Dokument steht unter MIT-0. Frei nutzbar, keine Attribution noetig.",
        S_FOOTER,
    ))

    doc.build(story)
    print(f"PDF: {OUT} ({os.path.getsize(OUT) // 1024} KB)")


if __name__ == "__main__":
    build()
