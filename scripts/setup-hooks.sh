#!/usr/bin/env bash
# One-shot setup für versionierte Git-Hooks (S163).
# Idempotent: setzt core.hooksPath nur wenn noch nicht.
#
# Aufruf: bash scripts/setup-hooks.sh
set -euo pipefail
cd "$(dirname "$0")/.."
CURRENT=$(git config --get core.hooksPath 2>/dev/null || true)
if [ "$CURRENT" = "scripts/git-hooks" ]; then
    echo "[setup-hooks] core.hooksPath already set to scripts/git-hooks ✓"
else
    git config core.hooksPath scripts/git-hooks
    echo "[setup-hooks] core.hooksPath set to scripts/git-hooks"
fi
echo "[setup-hooks] hooks active:"
ls -la scripts/git-hooks/ | tail -n +2
