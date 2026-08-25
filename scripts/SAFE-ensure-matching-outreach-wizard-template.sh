#!/usr/bin/env bash
# Email-Studio-Vorlage matching_outreach_wizard anlegen/aktualisieren.
#
# ucs5:
#   cd /mnt/public/udoo-reprap
#   git pull origin cursor/matching-shortlist-weights-1532
#   bash scripts/SAFE-ensure-matching-outreach-wizard-template.sh
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
SCRIPT="$REPO/scripts/ensure-matching-outreach-wizard-template.py"
PY="${PY:-/opt/abpe/venv311/bin/python}"

[[ -f "$SCRIPT" ]] || { echo "FAIL: $SCRIPT fehlt"; exit 1; }
[[ -d "$BACKEND" ]] || { echo "FAIL: $BACKEND fehlt"; exit 1; }

cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"

echo "→ Upsert matching_outreach_wizard …"
"$PY" manage.py shell < "$SCRIPT"
echo "OK — Email Studio → Vorlagen → „Matching — Outreach-Wizard Anschreiben“"
echo "Identifier: matching_outreach_wizard"
