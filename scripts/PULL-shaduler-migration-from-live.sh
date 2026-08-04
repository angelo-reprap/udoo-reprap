#!/usr/bin/env bash
# Live-Migration 0001_initial.py zurück ins Repo-Share (exakte Datei, bereits applied).
# Immer mit git -C auf dem Share-Repo aufrufen — nicht aus /opt/abpe/backend.
set -euo pipefail
LIVE="${LIVE:-/opt/abpe/backend/apps/abpe_shaduler/migrations/0001_initial.py}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
DEST="$REPO/Repo_abpe/abpe_shaduler/incoming/migrations/0001_initial.py"

if [[ ! -f "$LIVE" ]]; then
  echo "FAIL: $LIVE fehlt (vermutlich Sync --delete)."
  echo "Repo-Kopie nach Sync wiederherstellen, dann:"
  echo "  python manage.py makemigrations abpe_shaduler --dry-run"
  exit 1
fi
mkdir -p "$(dirname "$DEST")"
cp -a "$LIVE" "$DEST"
echo "OK → $DEST ($(wc -l < "$DEST") Zeilen)"
echo "Danach auf dem Share committen/pushen, oder Datei hier posten."
