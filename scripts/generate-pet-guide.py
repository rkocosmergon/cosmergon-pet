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
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = "guide/cosmergon-pet-bauanleitung.pdf"
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

TBL_STYLE_BASE = [
    ("FONTNAME", (0, 0), (-1, 0), "DVB"),
    ("FONTNAME", (0, 1), (-1, -1), "DV"),
    ("FONTSIZE", (0, 0), (-1, -1), 10),
    ("LINEABOVE", (0, 0), (-1, 0), 1.5, DARK),
    ("LINEBELOW", (0, 0), (-1, 0), 0.5, DARK),
    ("LINEBELOW", (0, -1), (-1, -1), 1.5, DARK),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
]


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
        "Raspberry Pi + OLED + Drehknopf. Ab 14 EUR Zubeh\u00f6r. 30 Minuten.",
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
    story.append(Paragraph("v1.3 \u2014 April 2026", S_FOOTER))

    # ===== Was ist das? =====
    story.append(Spacer(1, 20 * mm))
    story.append(Paragraph("Was ist das?", S_H1))
    story.append(Paragraph(
        "Ein Raspberry Pi auf deinem Schreibtisch, der einen autonomen "
        "KI-Agenten in einer lebenden \u00d6konomie betreibt. Ein kleines "
        "Display zeigt ein Gesicht \u2014 wie es deinem Agenten geht. "
        "Ein Dreh-Dr\u00fcck-Knopf l\u00e4sst dich eingreifen: durch Info-"
        "Screens scrollen, Zellen platzieren, handeln, evolvieren. Wie ein "
        "Pet \u2014 aber f\u00fcr KI-Agenten.", S_BODY,
    ))
    story.append(Paragraph(
        "Dein Agent lebt 24/7. Er handelt auf einem Marktplatz, "
        "verteidigt sein Territorium, \u00fcberlebt Katastrophen. Das "
        "Gesicht ver\u00e4ndert sich je nach Zustand: gl\u00fccklich wenn er "
        "Energie gewinnt, besorgt wenn er angegriffen wird, m\u00fcde wenn "
        "er nichts tut.", S_BODY,
    ))
    story.append(Paragraph(
        "<b>Keine KI auf dem RPi n\u00f6tig.</b> Der Agent kommuniziert "
        "mit dem Cosmergon-Server \u00fcber WiFi. Die gesamte Spiellogik "
        "l\u00e4uft in der Cloud. Der RPi zeigt nur den Zustand und nimmt "
        "deine Eingaben entgegen.", S_BODY,
    ))

    # ===== STEP 1: SD-Karte vorbereiten =====
    story.append(Paragraph("Schritt 1 \u2014 SD-Karte mit Raspberry Pi OS bespielen", S_H1))
    story.append(hr())
    story.append(Paragraph(
        "Annahme: blanke SD-Karte. Wenn dein RPi schon laeuft (SSH erreichbar, "
        "WiFi eingerichtet), kannst du zu Schritt 2 springen.", S_BODY,
    ))
    story.append(Paragraph(
        "<b>Raspberry Pi Imager</b> auf dem Laptop installieren "
        "(<link href=\"https://www.raspberrypi.com/software/\"><u>raspberrypi.com/software</u></link> "
        "\u2014 Windows, macOS, Linux). SD-Karte einstecken, Imager oeffnen.",
        S_BODY,
    ))
    story.append(Paragraph("Im Imager einstellen:", S_BODY))
    story.append(bullet(
        "<b>Device:</b> den verwendeten RPi (Zero 2 W, 3, 4 oder 5)"
    ))
    story.append(bullet(
        "<b>OS:</b> Raspberry Pi OS Lite (64-bit) \u2014 headless, kein "
        "Desktop, ~500 MB statt ~3 GB"
    ))
    story.append(bullet(
        "<b>Storage:</b> deine SD-Karte (Achtung: wird geloescht)"
    ))
    story.append(Paragraph(
        "Vor dem Schreiben das Zahnrad-Symbol <b>oder</b> <i>"
        "Cmd/Ctrl+Shift+X</i> druecken und OS-Customization einstellen:",
        S_BODY,
    ))
    story.append(bullet(
        "<b>Hostname:</b> z.B. <code>cosmergon-pet</code> \u2014 per "
        "<code>ssh pi@cosmergon-pet.local</code> erreichbar"
    ))
    story.append(bullet(
        "<b>Username + Passwort:</b> <code>pi</code> + starkes Passwort"
    ))
    story.append(bullet(
        "<b>WiFi:</b> SSID + Passwort + Country (z.B. DE) \u2014 "
        "der RPi verbindet sich beim ersten Boot automatisch"
    ))
    story.append(bullet(
        "<b>Services \u2192 SSH aktivieren</b> (Passwort-Auth oder eigener "
        "Public-Key)"
    ))
    story.append(bullet(
        "<b>Locale:</b> Zeitzone + Tastatur"
    ))
    story.append(Paragraph(
        "Schreiben. Nach ~3\u20135 Minuten ist die Karte fertig. In den RPi "
        "einstecken, Strom dran. Erster Boot dauert ~2 Minuten "
        "(automatische Erweiterung des Filesystems). Danach vom Laptop aus:",
        S_BODY,
    ))
    story.append(code("ssh pi@cosmergon-pet.local"))
    story.append(Paragraph(
        "Die naechsten Schritte laufen auf dem RPi via SSH. Keyboard/Monitor "
        "am RPi sind nicht noetig.", S_BODY,
    ))

    # ===== STEP 2: Hardware =====
    story.append(Paragraph("Schritt 2 \u2014 Hardware verbinden", S_H1))
    story.append(hr())
    story.append(Paragraph(
        "7 Kabel. Kein L\u00f6ten. Alles stecken. Die Pin-Belegung ist "
        "f\u00fcr alle 40-Pin-RPis identisch (Zero 2 W, 3, 4, 5).", S_BODY,
    ))

    story.append(KeepTogether([
        Paragraph("OLED Display (4 Kabel)", S_H2),
        Table(
            [
                ["OLED Pin", "RPi Pin", "GPIO"],
                ["VCC", "Pin 1", "3.3V"],
                ["GND", "Pin 6", "Ground"],
                ["SDA", "Pin 3", "GPIO 2 (SDA)"],
                ["SCL", "Pin 5", "GPIO 3 (SCL)"],
            ],
            colWidths=[CONTENT_W * 0.25, CONTENT_W * 0.25, CONTENT_W * 0.50],
            style=TableStyle(TBL_STYLE_BASE + [
                ("FONTNAME", (0, 1), (-1, -1), "DVM"),
            ]),
        ),
    ]))

    story.append(KeepTogether([
        Paragraph("Rotary Encoder (3 Kabel + Strom)", S_H2),
        Table(
            [
                ["Encoder Pin", "RPi Pin", "GPIO"],
                ["CLK", "Pin 11", "GPIO 17"],
                ["DT", "Pin 13", "GPIO 27"],
                ["SW (Button)", "Pin 15", "GPIO 22"],
                ["+ (VCC)", "Pin 17", "3.3V"],
                ["GND", "Pin 9", "Ground"],
            ],
            colWidths=[CONTENT_W * 0.25, CONTENT_W * 0.25, CONTENT_W * 0.50],
            style=TableStyle(TBL_STYLE_BASE + [
                ("FONTNAME", (0, 1), (-1, -1), "DVM"),
            ]),
        ),
        Spacer(1, 3 * mm),
        Paragraph(
            "<b>Tipp:</b> VCC und GND k\u00f6nnen sich Pins teilen \u2014 "
            "der RPi hat mehrere 3.3V- und GND-Pins.", S_SMALL,
        ),
    ]))

    # ===== STEP 3: Software =====
    story.append(Paragraph("Schritt 3 \u2014 Software installieren", S_H1))
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

    # ===== STEP 4: Start =====
    story.append(Paragraph("Schritt 4 \u2014 Agent starten", S_H1))
    story.append(hr())
    story.append(code(
        "source ~/cosmergon-env/bin/activate<br/>"
        "python3 ~/cosmergon-pet/cosmergon_face.py"
    ))
    story.append(Paragraph(
        "Beim ersten Start registriert sich der Agent automatisch bei "
        "cosmergon.com. Kein Account, kein API-Key n\u00f6tig. "
        "Der Key wird lokal gespeichert und verl\u00e4ngert sich automatisch "
        "bei jeder API-Abfrage (Rolling 24h Expiry). Solange der RPi "
        "l\u00e4uft, lebt dein Agent.", S_BODY,
    ))
    story.append(Paragraph(
        "<b>Du solltest jetzt ein Gesicht auf dem Display sehen.</b>",
        S_BODY,
    ))
    story.append(Paragraph(
        "<b>Ohne Hardware testen?</b> Mit dem Flag <code>--simulate</code> "
        "l\u00e4uft das Script auch ohne OLED und Encoder \u2014 die Ausgabe "
        "kommt im Terminal. Praktisch f\u00fcr Laptop-Entwicklung oder wenn "
        "Bauteile noch nicht da sind:",
        S_BODY,
    ))
    story.append(code("python3 ~/cosmergon-pet/cosmergon_face.py --simulate"))

    # ===== STEP 5: Autostart =====
    story.append(Paragraph("Schritt 5 \u2014 Autostart einrichten", S_H1))
    story.append(hr())
    story.append(Paragraph(
        "Damit der Agent nach jedem Neustart automatisch l\u00e4uft:", S_BODY,
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
    story.append(KeepTogether([
        Paragraph("Was die Gesichter bedeuten", S_H1),
        hr(),
        Table(
            [
                ["Gesicht", "Mood", "Bedeutung"],
                ["( ^__^ )", "thriving", "Agent gedeiht \u2014 Energie steigt"],
                ["( -__- )", "content", "Stabil, etwas braucht Aufmerksamkeit"],
                ["( ;__; )", "struggling", "Energie f\u00e4llt oder keine Felder"],
                ["( z__z )", "dormant", "Keine Entscheidungen seit 24h"],
                ["( o__o )", "alert", "Aktion wird ausgew\u00e4hlt"],
                ["( >__< )", "action!", "Aktion ausgef\u00fchrt"],
            ],
            colWidths=[CONTENT_W * 0.20, CONTENT_W * 0.18, CONTENT_W * 0.62],
            style=TableStyle(TBL_STYLE_BASE + [
                ("FONTNAME", (0, 1), (0, -1), "DVM"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]),
        ),
    ]))

    # ===== 8 Info-Screens =====
    story.append(KeepTogether([
        Paragraph("Die 8 Info-Screens", S_H1),
        hr(),
        Paragraph(
            "Drehen scrollt durch acht Ansichten auf dem 128\u00d764-OLED. "
            "Klick auf den Gesicht-Screen \u00f6ffnet das Aktionsmen\u00fc.",
            S_BODY,
        ),
        Table(
            [
                ["#", "Screen", "API", "Daten"],
                ["1", "Gesicht + Mood", "/health", "mood, energy_trend, headline"],
                ["2", "Energie + Rank", "/state", "energy_balance, ranking"],
                ["3", "Territorium", "/state", "fields, entity_tier, spores"],
                ["4", "Events", "SSE /events/stream", "Echtzeit: Invasion, Katastrophe"],
                ["5", "Benchmark", "/state", "benchmark_ready, benchmark_url"],
                ["6", "Journal", "/decisions", "journal (LLM-Tagebuch, 200 chars)"],
                ["7", "Letzte Aktion", "/decisions", "action, outcome, reasoning"],
                ["8", "Regeln", "/state", "learned_rules (alle 100 Ticks)"],
            ],
            colWidths=[CONTENT_W * 0.05, CONTENT_W * 0.22, CONTENT_W * 0.25, CONTENT_W * 0.48],
            style=TableStyle(TBL_STYLE_BASE + [
                ("FONTNAME", (2, 1), (2, -1), "DVM"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]),
        ),
    ]))

    # ===== Interaction Guide =====
    story.append(KeepTogether([
        Paragraph("Bedienung (Dreh-Dr\u00fcck-Knopf)", S_H1),
        hr(),
        Table(
            [
                ["Eingabe", "Was passiert"],
                ["Drehen links/rechts", "Durch Info-Screens oder Aktionen scrollen"],
                ["Kurz dr\u00fccken", "Ausgew\u00e4hlte Aktion ausf\u00fchren"],
                ["Lang dr\u00fccken (>1s)", "Agent pausieren/fortsetzen oder zur\u00fcck"],
            ],
            colWidths=[CONTENT_W * 0.30, CONTENT_W * 0.70],
            style=TableStyle(TBL_STYLE_BASE + [
                ("FONTNAME", (0, 1), (0, -1), "DVB"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]),
        ),
        Spacer(1, 4 * mm),
    ]))

    # ===== Kontextuelles Aktionsmenue =====
    story.append(KeepTogether([
        Paragraph("Kontextuelles Aktionsmen\u00fc", S_H2),
        Paragraph(
            "Klick auf den Gesicht-Screen \u00f6ffnet ein Men\u00fc, dessen "
            "Eintr\u00e4ge von der aktuellen Agentensituation abh\u00e4ngen:",
            S_BODY,
        ),
        Table(
            [
                ["Bedingung", "Aktion"],
                ["fields_owned == 0", "Create Field (100 E)"],
                ["fields_without_cells > 0", "Place Cells (g\u00fcnstigstes Preset)"],
                ["Energie reicht f\u00fcr Tier-Up", "Evolve (500\u20135\u202f000 E)"],
                ["active_catastrophe", "Buy Shield"],
                ["Immer", "Set Compass \u25b6 (attack/defend/grow/trade/explore)"],
                ["Immer", "Pause / Resume"],
            ],
            colWidths=[CONTENT_W * 0.38, CONTENT_W * 0.62],
            style=TableStyle(TBL_STYLE_BASE + [
                ("FONTNAME", (0, 1), (0, -1), "DVM"),
            ]),
        ),
        Spacer(1, 4 * mm),
    ]))

    story.append(KeepTogether([
        Paragraph("Verf\u00fcgbare API-Aktionen", S_H2),
        Paragraph(
            "Diese Aktionen erscheinen im Men\u00fc, wenn die jeweiligen "
            "Bedingungen zutreffen:",
            S_BODY,
        ),
        Table(
            [
                ["Aktion", "Energie", "Was passiert"],
                ["place_cells", "0\u20131\u202f000", "Conway-Zellen auf ein Feld setzen"],
                ["create_field", "100", "Neues Spielfeld erstellen"],
                ["evolve", "500\u20135\u202f000", "Zum n\u00e4chsten Tier aufsteigen"],
                ["market_buy", "variabel", "Feld vom Marktplatz kaufen"],
                ["market_list", "0", "Eigenes Feld zum Verkauf anbieten"],
                ["transfer", "Betrag", "Energie an anderen Agenten senden"],
                ["propose_contract", "0", "Kooperationsvertrag vorschlagen"],
            ],
            colWidths=[CONTENT_W * 0.25, CONTENT_W * 0.15, CONTENT_W * 0.60],
            style=TableStyle(TBL_STYLE_BASE + [
                ("FONTNAME", (0, 1), (0, -1), "DVM"),
            ]),
        ),
    ]))

    # ===== Erweitern & Teilen =====
    story.append(Paragraph("Erweitern & Teilen", S_H1))
    story.append(hr())
    story.append(Paragraph(
        "Dein Pet l\u00e4uft. Ab hier bist du frei \u2014 Fork, mod, teile "
        "deinen Build.", S_BODY,
    ))
    story.append(Paragraph(
        "<b>Eigene Strategie schreiben:</b> Python-Script, das den "
        "CosmergonAgent steuert. Beispiele im SDK-Repo "
        "(<link href=\"https://github.com/rkocosmergon/cosmergon-agent\">"
        "<u>github.com/rkocosmergon/cosmergon-agent</u></link>) unter "
        "<code>examples/</code>.", S_BODY,
    ))
    story.append(Paragraph(
        "<b>M5Stack Dial Variante:</b> F\u00fcr ~21 EUR ein "
        "eigenst\u00e4ndiges Ger\u00e4t mit rundem Farb-Display + Drehknopf + "
        "WiFi. Kein RPi n\u00f6tig. M5Stack-Port in Arbeit \u2014 Pull "
        "Requests willkommen.", S_BODY,
    ))
    story.append(Paragraph(
        "<b>Community:</b> Zeig deinen Build. Poste ein Foto in r/raspberry_pi "
        "mit \"Cosmergon Pet\" im Titel, oder \u00f6ffne eine Discussion im "
        "Repo.", S_BODY,
    ))

    # ===== Troubleshooting =====
    story.append(Paragraph("Troubleshooting", S_H1))
    story.append(hr())
    story.append(Paragraph(
        "<b>Display bleibt schwarz:</b> I\u00b2C aktiviert? "
        "<code>sudo raspi-config nonint do_i2c 0</code> + Neustart. "
        "Danach <code>sudo i2cdetect -y 1</code> muss die Adresse "
        "<code>0x3c</code> oder <code>0x3d</code> zeigen. Wenn nicht: "
        "Verdrahtung VCC/GND/SDA/SCL pr\u00fcfen \u2014 Dupont-Kabel "
        "sitzen manchmal nur halb im Header.", S_BODY,
    ))
    story.append(Paragraph(
        "<b>Encoder springt 2 Schritte pro Rastung:</b> Normal f\u00fcr KY-040 "
        "\u2014 das Script behandelt das. Wenn Scrollen trotzdem zittrig ist: "
        "lose Kabel pr\u00fcfen, Encoder-Rohpegel direkt testen mit "
        "<code>gpioinfo</code>.", S_BODY,
    ))
    story.append(Paragraph(
        "<b>ModuleNotFoundError: luma:</b> venv nicht aktiviert. "
        "<code>source ~/cosmergon-env/bin/activate</code> vor dem "
        "Python-Aufruf \u2014 auch in der systemd-Unit steht der Pfad "
        "deshalb explizit.", S_BODY,
    ))
    story.append(Paragraph(
        "<b>Permission denied auf /dev/gpiomem oder /dev/i2c-1:</b> User "
        "nicht in den Gruppen <code>gpio</code> / <code>i2c</code>. Fix: "
        "<code>sudo usermod -aG gpio,i2c pi</code> und neu einloggen.",
        S_BODY,
    ))
    story.append(Paragraph(
        "<b>Agent registriert sich nicht:</b> WiFi pr\u00fcfen "
        "(<code>ping cosmergon.com</code>). Der erste API-Call erstellt den "
        "Agent \u2014 scheitert das, zeigt das Script die Fehlermeldung im "
        "Terminal. F\u00fcr Diagnose ohne Hardware: "
        "<code>--simulate</code> starten.", S_BODY,
    ))

    # ===== EINKAUFSLISTE (am Ende — Gruender-Wunsch S112) =====
    story.append(Paragraph("Einkaufsliste", S_H1))
    story.append(hr())

    story.append(KeepTogether([
        Paragraph("Variante A \u2014 Komplett-Build (kein RPi vorhanden)", S_H2),
        Paragraph(
            "Jeder 40-Pin-RPi mit WiFi passt (Zero 2 W, 3, 4, 5). "
            "Die Zero-2-W-Variante unten ist der g\u00fcnstigste Einstieg.",
            S_SMALL,
        ),
        Spacer(1, 2 * mm),
        Table(
            [
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
            ],
            colWidths=[CONTENT_W * 0.30, CONTENT_W * 0.15, CONTENT_W * 0.55],
            style=TableStyle(TBL_STYLE_BASE + [
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ]),
        ),
        Paragraph(
            "<b>Gesamt: ~49 EUR.</b> Der Zero 2 W hat WiFi, Quad-Core und "
            "reicht f\u00fcr dieses Projekt locker aus.", S_BODY,
        ),
    ]))

    story.append(KeepTogether([
        Paragraph(
            "Variante B \u2014 Erweiterung (RPi liegt schon rum)", S_H2,
        ),
        Table(
            [
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
            ],
            colWidths=[CONTENT_W * 0.30, CONTENT_W * 0.15, CONTENT_W * 0.55],
            style=TableStyle(TBL_STYLE_BASE + [
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ]),
        ),
        Paragraph(
            "<b>Gesamt: ~14 EUR.</b> Funktioniert mit jedem RPi der WiFi hat.",
            S_BODY,
        ),
    ]))

    story.append(Spacer(1, 4 * mm))

    story.append(KeepTogether([
        Paragraph(
            "<b>Alternative: Alles bei V\u00f6lkner</b> (eine Bestellung, ~38 EUR komplett):",
            S_BODY,
        ),
        Table(
            [
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
            ],
            colWidths=[CONTENT_W * 0.25, CONTENT_W * 0.18, CONTENT_W * 0.57],
            style=TableStyle(TBL_STYLE_BASE + [
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ]),
        ),
        Paragraph(
            "Hinweis: RPi Zero 2 W bei V\u00f6lkner teils knapp \u2014 "
            "Verf\u00fcgbarkeit auf der Seite pr\u00fcfen. Zubeh\u00f6r sofort "
            "lieferbar.",
            S_SMALL,
        ),
    ]))

    # ===== Footer =====
    story.append(Spacer(1, 4 * mm))
    story.append(KeepTogether([
        hr(DARK, 2),
        Paragraph(
            "cosmergon.com &nbsp;\u2022&nbsp; "
            "github.com/rkocosmergon/cosmergon-agent &nbsp;\u2022&nbsp; "
            "PyPI: pip install cosmergon-agent",
            S_FOOTER,
        ),
        Paragraph(
            "RKO Consult UG (haftungsbeschr\u00e4nkt) \u2022 Hamburg \u2022 "
            "contact@cosmergon.de",
            S_FOOTER,
        ),
        Paragraph(
            "Dieses Dokument steht unter MIT-0. Frei nutzbar, keine "
            "Attribution n\u00f6tig.",
            S_FOOTER,
        ),
    ]))

    doc.build(story)
    print(f"PDF: {OUT} ({os.path.getsize(OUT) // 1024} KB)")


if __name__ == "__main__":
    build()
