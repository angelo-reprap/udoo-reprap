#!/usr/bin/env bash
# Deploy CRM Theme Phase 2 (Lesbarkeit Dark Mode)
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
INCOMING="$(cd "$(dirname "$0")" && pwd)"
STATIC="${BACKEND}/apps/abpe_crm/static/abpe_crm"
ARCHIV="${BACKEND}/Archiv"

echo "=== CRM Theme Phase 2 Deploy (Lesbarkeit) ==="

cp "${INCOMING}/css/core-theme.css" "${STATIC}/css/core-theme.css"
cp "${INCOMING}/css/mod-crm.css" "${STATIC}/css/mod-crm.css"
cp "${INCOMING}/css/ui-components.css" "${STATIC}/css/ui-components.css"
cp "${INCOMING}/js/mod-crm-edit.js" "${STATIC}/js/mod-crm-edit.js"
cp "${INCOMING}/js/mod-crm-kunden.js" "${STATIC}/js/mod-crm-kunden.js"
cp "${INCOMING}/js/mod-crm-berater.js" "${STATIC}/js/mod-crm-berater.js"

if [[ -x "${ARCHIV}/backup_restore.py" ]]; then
  NOTE="${NOTE:-vor crm-theme-phase2}"
  for rel in \
    apps/abpe_crm/static/abpe_crm/css/core-theme.css \
    apps/abpe_crm/static/abpe_crm/css/mod-crm.css \
    apps/abpe_crm/static/abpe_crm/css/ui-components.css \
    apps/abpe_crm/static/abpe_crm/js/mod-crm-edit.js \
    apps/abpe_crm/static/abpe_crm/js/mod-crm-kunden.js \
    apps/abpe_crm/static/abpe_crm/js/mod-crm-berater.js; do
    [[ -f "${BACKEND}/${rel}" ]] && python3 "${ARCHIV}/backup_restore.py" -save "${rel}" -m "${NOTE}" || true
  done
fi

echo "Done. collectstatic + restart abpe-django:"
echo "  cd ${BACKEND} && python manage.py collectstatic --noinput"
echo "  supervisorctl restart abpe-django"
