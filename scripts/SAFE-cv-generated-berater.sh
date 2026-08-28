#!/usr/bin/env bash
# cv_generated_berater: Button weg, PDF als Anhang (lokal, kein WAN→LAN).
#
# ucs5, venv, /opt/abpe/backend:
#   git -C /mnt/public/udoo-reprap fetch origin cursor/crm-profilupdate-text-ee01
#   bash <(git -C /mnt/public/udoo-reprap show origin/cursor/crm-profilupdate-text-ee01:scripts/SAFE-cv-generated-berater.sh)
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/crm-profilupdate-text-ee01}"
PY="${PY:-/opt/abpe/venv311/bin/python}"

[[ -d "$BACKEND" ]] || { echo "FAIL: $BACKEND fehlt"; exit 1; }

cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"

echo "→ fetch origin/$BRANCH …"
git -C "$REPO" fetch origin "$BRANCH"

echo "→ 1/2 Vorlage ohne Portal-Link …"
git -C "$REPO" show "origin/${BRANCH}:scripts/ensure-cv-generated-berater-template.py" | "$PY" manage.py shell

echo "→ 2/2 Email Studio: PDF-Anhang (Backup + Patch) …"
git -C "$REPO" show "origin/${BRANCH}:scripts/live_patch_email_studio_attachments.py" | "$PY"

echo
echo "OK — cv_generated_berater ohne Button, Anhang über lokalen Dateipfad"
echo "Pflicht: supervisorctl restart abpe-django abpe-celery"
echo "Danach Ctrl+F5 im Email-Studio"
