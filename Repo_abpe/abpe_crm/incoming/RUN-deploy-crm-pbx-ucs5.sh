#!/usr/bin/env bash
# CRM PBX JS: Git → Live static (ucs5)
#
#   cd /mnt/public/udoo-reprap && git pull
#   bash Repo_abpe/abpe_crm/incoming/RUN-deploy-crm-pbx-ucs5.sh
#   cd /opt/abpe/backend && python manage.py collectstatic --noinput
#
# Vollständiges Timezone-Deploy (JS + Templates + Backend-Patch):
#   bash Repo_abpe/abpe_crm/incoming/RUN-deploy-crm-timezone-ucs5.sh

set -euo pipefail

REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
DEST_DIR="${ABPE_CRM_STATIC:-/opt/abpe/backend/apps/abpe_crm/static/abpe_crm/js}"

for f in mod-crm-pbx.js core-timezone.js; do
  SRC="${REPO}/Repo_abpe/abpe_crm/incoming/js/${f}"
  DEST="${DEST_DIR}/${f}"
  if [[ ! -f "$SRC" ]]; then
    echo "FEHLER: $SRC fehlt — git pull?" >&2
    exit 1
  fi
  cp -a "$SRC" "$DEST"
  echo "OK: $SRC -> $DEST"
done

if grep -q "_mmNotifyCommit" "${DEST_DIR}/mod-crm-pbx.js" && grep -q "action === 'reschedule'" "${DEST_DIR}/mod-crm-pbx.js"; then
  echo "OK: Einladungs-Fix (_mmNotifyCommit) in Live-JS"
else
  echo "WARN: Einladungs-Fix evtl. nicht in Datei" >&2
fi

if grep -q "timezoneManager" "${DEST_DIR}/core-timezone.js" 2>/dev/null; then
  echo "OK: core-timezone.js deployed"
fi

echo "Danach: cd /opt/abpe/backend && python manage.py collectstatic --noinput"
