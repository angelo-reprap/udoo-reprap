#!/usr/bin/env bash
# Email-Studio-Vorlagen für alle Matching-Kanban-Stufen anlegen/aktualisieren.
#
# ucs5:
#   cd /mnt/public/udoo-reprap
#   git pull origin cursor/matching-stage-mail-templates-1532
#   bash scripts/SAFE-ensure-matching-stage-templates.sh
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
SCRIPT="$REPO/scripts/ensure-matching-stage-templates.py"
PY="${PY:-/opt/abpe/venv311/bin/python}"

[[ -f "$SCRIPT" ]] || { echo "FAIL: $SCRIPT fehlt"; exit 1; }
[[ -d "$BACKEND" ]] || { echo "FAIL: $BACKEND fehlt"; exit 1; }

cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"

echo "→ Upsert Matching-Stage-Vorlagen (Email Studio) …"
"$PY" manage.py shell < "$SCRIPT"
echo "OK — u. a. matching_present_to_client (Interesse → Beim Kunden)"
echo "Danach: Browser Ctrl+F5, erneuter Mail-Dialog aus Spalte Interesse"
