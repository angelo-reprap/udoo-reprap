#!/usr/bin/env bash
# Ungenutzte E-Mail-Vorlagen archivieren (kein Hard-Delete).
#
# Email Studio: test, cv_generated_berater_copy → ARCHIVED (sonst DRAFT)
# Alte Tabelle abpe_matching_workflow.EmailTemplate: is_active=False
#
# CRM, Intake, MeetMe und die 7 Matching-Stage-Vorlagen bleiben aktiv.
#
# ucs5 — Datei von origin lesen (lokales git oft divergent):
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/email-matching-layout-ee01
#   bash scripts/SAFE-archive-unused-email-templates.sh
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/email-matching-layout-ee01}"
PY="${PY:-/opt/abpe/venv311/bin/python}"
REL="scripts/archive-unused-email-templates.py"

[[ -d "$BACKEND" ]] || { echo "FAIL: $BACKEND fehlt"; exit 1; }

cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"

echo "→ fetch origin/$BRANCH …"
git -C "$REPO" fetch origin "$BRANCH"

echo "→ Archivieren ungenutzter Vorlagen (kein Delete) …"
git -C "$REPO" show "origin/${BRANCH}:${REL}" | "$PY" manage.py shell
echo "OK — Email Studio: Filter „Archiv“ prüfen; Matching-Admin: is_active=False"
echo "Danach: Browser Ctrl+F5"
