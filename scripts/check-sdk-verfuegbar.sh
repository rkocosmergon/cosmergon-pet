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

# Bewusst der /simple/-Index, NICHT die JSON-API: letztere liegt hinter einem
# CDN-Cache und meldete am 22.08.2026 noch 0.18.0, als 0.19.0 laengst
# ausgeliefert wurde. Ein Gate, das eine vorhandene Version fuer fehlend
# erklaert, blockiert grundlos — und wer das zweimal erlebt, umgeht es.
# /simple/ ist der Index, aus dem pip selbst aufloest: er ist die Wahrheit,
# an der das Release spaeter scheitern oder gelingen wird.
index=$(curl -sf "https://pypi.org/simple/cosmergon-agent/") || {
    echo "⚠️  PyPI nicht erreichbar — Pruefung uebersprungen"
    exit 0
}
auf_pypi=$(printf '%s' "$index" \
    | grep -oE 'cosmergon_agent-[0-9]+\.[0-9]+\.[0-9]+' \
    | sed 's/cosmergon_agent-//' | sort -V | tail -1)

echo "gefordert: $noetig   hoechste auf PyPI: $auf_pypi"

if printf '%s\n%s\n' "$noetig" "$auf_pypi" | sort -V -C; then
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
