#!/usr/bin/env bash
# Live-Migration 0001_initial.py zurück ins Repo-Share (exakte Datei, bereits applied).
set -euo pipefail
LIVE="${LIVE:-/opt/abpe/backend/apps/abpe_shaduler/migrations/0001_initial.py}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
DEST="$REPO/Repo_abpe/abpe_shaduler/incoming/migrations/0001_initial.py"

if [[ ! -f "$LIVE" ]]; then
  echo "FAIL: $LIVE fehlt — erst makemigrations auf Live."
  exit 1
fi
mkdir -p "$(dirname "$DEST")"
cp -a "$LIVE" "$DEST"
echo "OK → $DEST"
echo "Danach (Share): git add + commit auf cursor/abpe-shaduler-scaffold-7f07, oder Datei hier posten."
