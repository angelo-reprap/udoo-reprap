#!/usr/bin/env bash
# Email-Studio: crm_firmenprofil von origin einspielen.
#
# Erfolg: OK — crm_firmenprofil (Person / I&O / KI ausführlich)
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/crm-profilupdate-text-ee01}"
PY="${PY:-/opt/abpe/venv311/bin/python}"
REL="scripts/ensure-crm-firmenprofil-template.py"

[[ -d "$BACKEND" ]] || { echo "FAIL: $BACKEND fehlt"; exit 1; }

cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"

echo "→ fetch origin/$BRANCH …"
git -C "$REPO" fetch origin "$BRANCH"

echo "→ Upsert crm_firmenprofil …"
git -C "$REPO" show "origin/${BRANCH}:${REL}" | "$PY" manage.py shell
echo "Danach: Browser Ctrl+F5, Email Studio Vorlage crm_firmenprofil"
