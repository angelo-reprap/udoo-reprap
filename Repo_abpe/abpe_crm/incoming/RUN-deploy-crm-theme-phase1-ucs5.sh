#!/usr/bin/env bash
# Deploy CRM Theme Phase 1 (core-theme + ui-components + base + header)
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
INCOMING="$(cd "$(dirname "$0")" && pwd)"
STATIC="${BACKEND}/apps/abpe_crm/static/abpe_crm"
TPL="${BACKEND}/apps/abpe_crm/templates/abpe_crm"
ARCHIV="${BACKEND}/Archiv"

echo "=== CRM Theme Phase 1 Deploy ==="

cp "${INCOMING}/css/core-theme.css" "${STATIC}/css/core-theme.css"
cp "${INCOMING}/css/ui-components.css" "${STATIC}/css/ui-components.css"
cp "${INCOMING}/js/core-theme.js" "${STATIC}/js/core-theme.js"
cp "${INCOMING}/templates/abpe_crm/base.html" "${TPL}/base.html"
cp "${INCOMING}/templates/abpe_crm/components/header.html" "${TPL}/components/header.html"

if [[ -x "${ARCHIV}/backup_restore.py" ]]; then
  NOTE="${NOTE:-vor crm-theme-phase1}"
  for rel in \
    apps/abpe_crm/static/abpe_crm/css/core-theme.css \
    apps/abpe_crm/static/abpe_crm/css/ui-components.css \
    apps/abpe_crm/static/abpe_crm/js/core-theme.js \
    apps/abpe_crm/templates/abpe_crm/base.html \
    apps/abpe_crm/templates/abpe_crm/components/header.html; do
    [[ -f "${BACKEND}/${rel}" ]] && python3 "${ARCHIV}/backup_restore.py" -save "${rel}" -m "${NOTE}" || true
  done
fi

echo "Done. collectstatic + restart abpe-django"
