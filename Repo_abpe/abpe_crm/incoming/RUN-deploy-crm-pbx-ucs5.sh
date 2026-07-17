#!/usr/bin/env bash
# CRM PBX JS: Git → Live static (ucs5)
#
#   cd /mnt/public/udoo-reprap && git pull
#   bash Repo_abpe/abpe_crm/incoming/RUN-deploy-crm-pbx-ucs5.sh
#   cd /opt/abpe/backend && python manage.py collectstatic --noinput

set -euo pipefail

REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
SRC="${REPO}/Repo_abpe/abpe_crm/incoming/js/mod-crm-pbx.js"
DEST="${ABPE_CRM_STATIC:-/opt/abpe/backend/apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js}"

if [[ ! -f "$SRC" ]]; then
  echo "FEHLER: $SRC fehlt — git pull?" >&2
  exit 1
fi

cp -a "$SRC" "$DEST"
echo "OK: $SRC -> $DEST"

if grep -q "_mmNotifyCommit" "$DEST" && grep -q "action === 'reschedule'" "$DEST"; then
  echo "OK: Einladungs-Fix (_mmNotifyCommit) in Live-JS"
else
  echo "WARN: Einladungs-Fix evtl. nicht in Datei" >&2
fi

echo "Danach: cd /opt/abpe/backend && python manage.py collectstatic --noinput"
