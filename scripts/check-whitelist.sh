#!/bin/bash
# PFLICHT: Prueft das Pet-Repo gegen die Public-Repo-Whitelist.
# WHITELIST-Ansatz: Nur explizit erlaubte Dateien duerfen im Repo sein.
# BANNED-Keywords: Infrastruktur, Secrets, Business-Interna, interne URLs.
# Exit 1 bei Verstoss. BLOCKING in CI.
#
# Aufruf:
#   bash scripts/check-whitelist.sh              (laeuft im repo-root)
#   bash scripts/check-whitelist.sh /pfad/zum/repo

set -euo pipefail

# Script liegt in $REPO/scripts/ — wenn kein Arg gegeben, leite $REPO
# aus dem Script-Pfad ab (nicht aus $PWD, sonst kollidiert das beim
# Aufruf aus einem anderen Repo-Checkout).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${1:-$(dirname "$SCRIPT_DIR")}"
ERRORS=0

echo "=== Cosmergon Pet Whitelist-Check: $REPO ==="
echo ""

# ================================================================
# 1. Pfad-Whitelist — nur diese Dateien duerfen im Repo sein
# ================================================================
ALLOWED_PATTERNS=(
    "README\.md"
    "LICENSE"
    "LICENSES/.+\.txt"
    "NOTICE"
    "CHANGELOG\.md"
    "CONTRIBUTING\.md"
    "CODE_OF_CONDUCT\.md"
    "SECURITY\.md"
    "pyproject\.toml"
    "\.gitignore"
    "\.ruff\.toml"
    "\.pre-commit-config\.yaml"
    "src/cosmergon_pet/[A-Za-z0-9_]+\.py"
    "src/cosmergon_pet/llm/[A-Za-z0-9_]+\.py"
    "scripts/[A-Za-z0-9_.-]+\.(sh|py)"
    "install/[A-Za-z0-9_.-]+\.(txt|sh)"
    "install/systemd/[A-Za-z0-9_.-]+\.service"
    "hardware/[A-Za-z0-9_./-]+\.(md|svg|png|jpg|fzz|fzpz)"
    "hardware/images/[A-Za-z0-9_./-]+\.(png|jpg|jpeg|svg)"
    "guide/[A-Za-z0-9_./-]+\.(pdf|md)"
    "docs/[A-Za-z0-9_./-]+\.(md|svg|png|jpg|jpeg)"
    "docs/images/[A-Za-z0-9_./-]+\.(png|jpg|jpeg|svg|gif)"
    "\.github/[A-Za-z0-9_./-]+\.(yml|yaml|md)"
    "tests/[A-Za-z0-9_/]+\.py"
    "tests/conftest\.py"
)

echo "--- 1. Pfad-Whitelist ---"
while IFS= read -r file; do
    allowed=false
    for pattern in "${ALLOWED_PATTERNS[@]}"; do
        if echo "$file" | grep -qE "^${pattern}$"; then
            allowed=true
            break
        fi
    done
    if [ "$allowed" = false ]; then
        echo "BLOCKER: '$file' ist NICHT in der Whitelist"
        ERRORS=$((ERRORS + 1))
    fi
done < <(cd "$REPO" && git ls-files)

if [ "$ERRORS" -eq 0 ]; then
    echo "  OK"
fi
echo ""

# ================================================================
# 2. Infrastruktur-Keywords — duerfen im Maker-Repo NICHT auftauchen
# ================================================================
echo "--- 2. Infrastruktur-Keywords ---"
INFRA_PATTERNS='178\.63\.233\.40|Hetzner|cosmergon-prod|cosmergon-staging|cosmergon-dev|gog-postgres-prod|gog-backend-prod|gog-redis-prod|/opt/cosmergon|supabase_admin|cosmergon_superuser|cosmergon_app'
if HITS=$(git -C "$REPO" grep -nE "$INFRA_PATTERNS" -- . ':!scripts/check-whitelist.sh' 2>/dev/null); then
    if [ -n "$HITS" ]; then
        echo "BLOCKER: Infrastruktur-Keyword gefunden:"
        echo "$HITS" | head -20
        ERRORS=$((ERRORS + 1))
    fi
fi
if [ "$ERRORS" -lt 2 ]; then echo "  OK"; fi
echo ""

# ================================================================
# 3. Secrets / Admin-Tokens
# ================================================================
echo "--- 3. Secrets / Admin-Tokens ---"
SECRET_PATTERNS='OPERATOR_TOKEN|X-Operator-Token|STRIPE_SECRET|SMTP_PASSWORD|SESSION_SECRET|JWT_PRIVATE_KEY|DB_PASSWORD|REDIS_PASSWORD|sk_live_|sk_test_[a-zA-Z0-9]{24}'
if HITS=$(git -C "$REPO" grep -nE "$SECRET_PATTERNS" -- . ':!scripts/check-whitelist.sh' 2>/dev/null); then
    if [ -n "$HITS" ]; then
        echo "BLOCKER: Secret-artiger String gefunden:"
        echo "$HITS" | head -20
        ERRORS=$((ERRORS + 1))
    fi
fi
if git -C "$REPO" grep -nE "$SECRET_PATTERNS" -- . ':!scripts/check-whitelist.sh' 2>/dev/null | grep -q .; then :; else echo "  OK"; fi
echo ""

# ================================================================
# 4. Business-Interna — Strategie-Dokumente, interne Konzepte
# ================================================================
echo "--- 4. Business-Keywords ---"
BIZ_PATTERNS='konzept-marktzugang|konzept-benchmark-service|konzept-cosmergon-pet|kommunikationsleitfaden-facetten|strategie-manifesto|pflichtenheft-|cos20/business'
if HITS=$(git -C "$REPO" grep -nE "$BIZ_PATTERNS" -- . ':!scripts/check-whitelist.sh' 2>/dev/null); then
    if [ -n "$HITS" ]; then
        echo "BLOCKER: Business-Interna-Verweis gefunden:"
        echo "$HITS" | head -20
        ERRORS=$((ERRORS + 1))
    fi
fi
if git -C "$REPO" grep -nE "$BIZ_PATTERNS" -- . ':!scripts/check-whitelist.sh' 2>/dev/null | grep -q .; then :; else echo "  OK"; fi
echo ""

# ================================================================
# 5. Persoenliche E-Mail-Adressen
# ================================================================
echo "--- 5. Persoenliche E-Mails ---"
# Erlaubt: contact@cosmergon.de, security@cosmergon.de
# Verboten: private E-Mails (rkmx, rkomx, privat), generische Provider
PRIV_EMAIL='rk@rkmx\.de|rk@rkomx\.com|@gmail\.com|@outlook\.com|@web\.de|@gmx\.'
if HITS=$(git -C "$REPO" grep -niE "$PRIV_EMAIL" -- . ':!scripts/check-whitelist.sh' 2>/dev/null); then
    if [ -n "$HITS" ]; then
        echo "BLOCKER: Persoenliche E-Mail-Adresse:"
        echo "$HITS" | head -10
        ERRORS=$((ERRORS + 1))
    fi
fi
if git -C "$REPO" grep -niE "$PRIV_EMAIL" -- . ':!scripts/check-whitelist.sh' 2>/dev/null | grep -q .; then :; else echo "  OK"; fi
echo ""

# ================================================================
# 6. Interne URLs / Admin-APIs
# ================================================================
echo "--- 6. Interne URLs / Admin-APIs ---"
INT_URL='/admin/config|/admin/inject|/admin/regenerate|grafana\.internal|prometheus:9090|alertmanager:9093'
if HITS=$(git -C "$REPO" grep -nE "$INT_URL" -- . ':!scripts/check-whitelist.sh' 2>/dev/null); then
    if [ -n "$HITS" ]; then
        echo "BLOCKER: Interne URL / Admin-API:"
        echo "$HITS" | head -10
        ERRORS=$((ERRORS + 1))
    fi
fi
if git -C "$REPO" grep -nE "$INT_URL" -- . ':!scripts/check-whitelist.sh' 2>/dev/null | grep -q .; then :; else echo "  OK"; fi
echo ""

# ================================================================
# Result
# ================================================================
echo "=== Result ==="
if [ "$ERRORS" -eq 0 ]; then
    echo "ALL CHECKS PASSED"
    exit 0
else
    echo "$ERRORS BLOCKER(S) FOUND — PUSH/MERGE BLOCKIERT"
    echo ""
    echo "Die Whitelist darf nur mit expliziter Freigabe des Maintainers"
    echo "erweitert werden (siehe CONTRIBUTING.md)."
    exit 1
fi
