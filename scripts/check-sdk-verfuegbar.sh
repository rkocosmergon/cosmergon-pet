#!/usr/bin/env bash
# Prueft, ob die in pyproject.toml geforderte cosmergon-agent-Mindestversion
# tatsaechlich auf PyPI liegt.
#
# WARUM ES DIESES SKRIPT GIBT (22.08.2026)
# Das Pet bekam `cosmergon-agent>=0.18.0`, weil es `get_balance_history()`
# braucht. Version 0.18.0 existierte da nur als Git-Tag — die Veroeffentlichung
# auf PyPI ist bewusst manuell (workflow_dispatch, Schutz gegen ungewollte
# Releases). Der Installer-Test baut aber ein echtes Pi-OS-Image und installiert
# daraus, also fiel er ueber die fehlende Version. Sichtbar wurde das erst nach
# 3,5 Minuten Image-Bau, in einer pip-Fehlermeldung.
#
# Die Reihenfolge ist damit fix: ERST das SDK veroeffentlichen, DANN das Pet
# releasen, das darauf zeigt.
set -euo pipefail

cd "$(dirname "$0")/.."

anforderung=$(grep -oE '"cosmergon-agent>=[0-9.]+"' pyproject.toml | head -1 | tr -d '"')
if [ -z "$anforderung" ]; then
    echo "❌ keine cosmergon-agent-Anforderung in pyproject.toml gefunden"
    exit 1
fi
noetig=${anforderung#cosmergon-agent>=}

auf_pypi=$(curl -sf "https://pypi.org/pypi/cosmergon-agent/json" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["info"]["version"])') || {
    echo "⚠️  PyPI nicht erreichbar — Pruefung uebersprungen"
    exit 0
}

echo "gefordert: $noetig   auf PyPI: $auf_pypi"

if python3 -c "
import sys
def teile(v): return [int(x) for x in v.split('.')]
sys.exit(0 if teile('$auf_pypi') >= teile('$noetig') else 1)
"; then
    echo "✅ SDK-Anforderung ist auf PyPI erfuellbar"
else
    cat <<MELDUNG
❌ cosmergon-agent $noetig liegt NICHT auf PyPI (dort: $auf_pypi).

   Ein Release des Pets waere nicht installierbar — der Installer-Test
   scheitert mit "No matching distribution found".

   Reihenfolge: ERST im SDK-Repo publish.yml ausloesen (manuell, Founder),
   PyPI abwarten, DANN das Pet releasen.
MELDUNG
    exit 1
fi
