#!/usr/bin/env bash
# Deploy EDMS Kleinigkeiten i18n (Stat-Labels, Doctype-Pills)
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
INCOMING="$(cd "$(dirname "$0")" && pwd)"
STATIC="${BACKEND}/apps/abpe_crm/static/abpe_crm"
TEMPLATES="${BACKEND}/apps/abpe_crm/templates/abpe_crm"
ARCHIV="${BACKEND}/Archiv"

echo "=== EDMS i18n Kleinigkeiten Deploy ==="

src="${INCOMING}/mod-edms.js"
if [[ -f "${INCOMING}/js/mod-edms.js" ]]; then src="${INCOMING}/js/mod-edms.js"; fi
echo "  -> js/mod-edms.js"
cp "${src}" "${STATIC}/js/mod-edms.js"

echo "  -> i18n/de/modules/crm_edms/crm_dms.json"
mkdir -p "${STATIC}/i18n/de/modules/crm_edms"
cp "${INCOMING}/i18n/de/modules/crm_edms/crm_dms.json" \
   "${STATIC}/i18n/de/modules/crm_edms/crm_dms.json"

if [[ -d "${TEMPLATES}/tabs" ]]; then
  echo "  -> templates/.../edms_tab.html"
  cp "${INCOMING}/templates/abpe_crm/tabs/edms_tab.html" "${TEMPLATES}/tabs/edms_tab.html"
fi

if [[ -x "${ARCHIV}/backup_restore.py" ]]; then
  NOTE="${NOTE:-vor edms-i18n-klein}"
  for rel in \
    apps/abpe_crm/static/abpe_crm/js/mod-edms.js \
    apps/abpe_crm/static/abpe_crm/i18n/de/modules/crm_edms/crm_dms.json \
    apps/abpe_crm/templates/abpe_crm/tabs/edms_tab.html; do
    [[ -f "${BACKEND}/${rel}" ]] && python3 "${ARCHIV}/backup_restore.py" -save "${rel}" -m "${NOTE}" || true
  done
fi

echo "Done. Run i18n_translator.py, collectstatic + restart."
