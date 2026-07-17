#!/usr/bin/env bash
# Deploy CRM Theme Phase 5 (CSS Cleanup: Duplikate, Token-Reihenfolge)
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
INCOMING="$(cd "$(dirname "$0")" && pwd)"
STATIC="${BACKEND}/apps/abpe_crm/static/abpe_crm"
TPL="${BACKEND}/apps/abpe_crm/templates/abpe_crm"
ARCHIV="${BACKEND}/Archiv"

echo "=== CRM Theme Phase 5 Deploy (CSS Cleanup) ==="

cp "${INCOMING}/css/core-base.css" "${STATIC}/css/core-base.css"
cp "${INCOMING}/css/core-gsearch.css" "${STATIC}/css/core-gsearch.css"
cp "${INCOMING}/css/mod-edms.css" "${STATIC}/css/mod-edms.css"
cp "${INCOMING}/templates/abpe_crm/base.html" "${TPL}/base.html"

# Alte Backup-Datei auf Live entfernen (nicht mehr im Repo)
rm -f "${STATIC}/css/mod-crm.css.before_restore"

if [[ -x "${ARCHIV}/backup_restore.py" ]]; then
  NOTE="${NOTE:-vor crm-theme-phase5}"
  for rel in \
    apps/abpe_crm/static/abpe_crm/css/core-base.css \
    apps/abpe_crm/static/abpe_crm/css/core-gsearch.css \
    apps/abpe_crm/static/abpe_crm/css/mod-edms.css \
    apps/abpe_crm/templates/abpe_crm/base.html; do
    [[ -f "${BACKEND}/${rel}" ]] && python3 "${ARCHIV}/backup_restore.py" -save "${rel}" -m "${NOTE}" || true
  done
fi

echo "Done. collectstatic + restart abpe-django:"
echo "  cd ${BACKEND} && python manage.py collectstatic --noinput"
echo "  supervisorctl restart abpe-django"
