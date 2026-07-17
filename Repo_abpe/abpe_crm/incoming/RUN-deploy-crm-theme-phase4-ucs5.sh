#!/usr/bin/env bash
# Deploy CRM Theme Phase 4 (EDMS/Dokumente Dark Mode + Typ-Icons)
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
INCOMING="$(cd "$(dirname "$0")" && pwd)"
STATIC="${BACKEND}/apps/abpe_crm/static/abpe_crm"
ARCHIV="${BACKEND}/Archiv"

echo "=== CRM Theme Phase 4 Deploy (EDMS/Dokumente) ==="

cp "${INCOMING}/css/mod-edms.css" "${STATIC}/css/mod-edms.css"
cp "${INCOMING}/js/mod-edms.js" "${STATIC}/js/mod-edms.js"

if [[ -x "${ARCHIV}/backup_restore.py" ]]; then
  NOTE="${NOTE:-vor crm-theme-phase4}"
  for rel in \
    apps/abpe_crm/static/abpe_crm/css/mod-edms.css \
    apps/abpe_crm/static/abpe_crm/js/mod-edms.js; do
    [[ -f "${BACKEND}/${rel}" ]] && python3 "${ARCHIV}/backup_restore.py" -save "${rel}" -m "${NOTE}" || true
  done
fi

echo "Done. collectstatic + restart abpe-django:"
echo "  cd ${BACKEND} && python manage.py collectstatic --noinput"
echo "  supervisorctl restart abpe-django"
