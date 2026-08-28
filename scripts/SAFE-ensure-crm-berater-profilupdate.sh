#!/usr/bin/env bash
# Email-Studio: crm_berater_profilupdate (Ton locker) von origin einspielen.
#
# Erfolg: OK — crm_berater_profilupdate (Ton locker)
#
# ucs5 (kein git pull, Working Tree oft divergent):
#   cd /opt/abpe/backend
#   git -C /mnt/public/udoo-reprap fetch origin cursor/crm-profilupdate-text-ee01
#   python manage.py shell < <(
#     git -C /mnt/public/udoo-reprap show origin/cursor/crm-profilupdate-text-ee01:scripts/ensure-crm-berater-profilupdate-template.py
#   )
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/crm-profilupdate-text-ee01}"
PY="${PY:-/opt/abpe/venv311/bin/python}"
REL="scripts/ensure-crm-berater-profilupdate-template.py"

[[ -d "$BACKEND" ]] || { echo "FAIL: $BACKEND fehlt"; exit 1; }

cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"

echo "→ fetch origin/$BRANCH …"
git -C "$REPO" fetch origin "$BRANCH"

echo "→ Upsert crm_berater_profilupdate …"
git -C "$REPO" show "origin/${BRANCH}:${REL}" | "$PY" manage.py shell
echo "Danach: Browser Ctrl+F5, Email Studio Vorlage crm_berater_profilupdate"
