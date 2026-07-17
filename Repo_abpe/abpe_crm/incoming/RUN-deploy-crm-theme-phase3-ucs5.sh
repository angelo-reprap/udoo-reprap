#!/usr/bin/env bash
# Deploy CRM Theme Phase 3 (Telefon/PBX Konferenz + E-Mail Kampagne)
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
INCOMING="$(cd "$(dirname "$0")" && pwd)"
STATIC="${BACKEND}/apps/abpe_crm/static/abpe_crm"
TPL="${BACKEND}/apps/abpe_crm/templates/abpe_crm"
ARCHIV="${BACKEND}/Archiv"

echo "=== CRM Theme Phase 3 Deploy (PBX/Konferenz) ==="

cp "${INCOMING}/css/core-theme.css" "${STATIC}/css/core-theme.css"
cp "${INCOMING}/css/mod-crm-pbx.css" "${STATIC}/css/mod-crm-pbx.css"
cp "${INCOMING}/js/mod-crm-pbx.js" "${STATIC}/js/mod-crm-pbx.js"
cp "${INCOMING}/templates/abpe_crm/tabs/emails_tab.html" "${TPL}/tabs/emails_tab.html"

if [[ -x "${ARCHIV}/backup_restore.py" ]]; then
  NOTE="${NOTE:-vor crm-theme-phase3}"
  for rel in \
    apps/abpe_crm/static/abpe_crm/css/core-theme.css \
    apps/abpe_crm/static/abpe_crm/css/mod-crm-pbx.css \
    apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js \
    apps/abpe_crm/templates/abpe_crm/tabs/emails_tab.html; do
    [[ -f "${BACKEND}/${rel}" ]] && python3 "${ARCHIV}/backup_restore.py" -save "${rel}" -m "${NOTE}" || true
  done
fi

echo "Done. collectstatic + restart abpe-django:"
echo "  cd ${BACKEND} && python manage.py collectstatic --noinput"
echo "  supervisorctl restart abpe-django"
