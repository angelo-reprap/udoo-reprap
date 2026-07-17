#!/usr/bin/env bash
# Deploy Telefon Statistik i18n (mod-crm-pbx.js + de/crm_telefon.json)
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
INCOMING="$(cd "$(dirname "$0")" && pwd)"
STATIC="${BACKEND}/apps/abpe_crm/static/abpe_crm"
TEMPLATES="${BACKEND}/apps/abpe_crm/templates/abpe_crm"
ARCHIV="${BACKEND}/Archiv"

echo "=== Telefon Statistik i18n Deploy ==="
echo "Source: ${INCOMING}"
echo "Target: ${STATIC}"

src="${INCOMING}/mod-crm-pbx.js"
if [[ -f "${INCOMING}/js/mod-crm-pbx.js" ]]; then src="${INCOMING}/js/mod-crm-pbx.js"; fi
echo "  -> js/mod-crm-pbx.js"
cp "${src}" "${STATIC}/js/mod-crm-pbx.js"

echo "  -> i18n/de/modules/crm_telefon/crm_telefon.json"
mkdir -p "${STATIC}/i18n/de/modules/crm_telefon"
cp "${INCOMING}/i18n/de/modules/crm_telefon/crm_telefon.json" \
   "${STATIC}/i18n/de/modules/crm_telefon/crm_telefon.json"

if [[ -d "${TEMPLATES}/tabs" ]]; then
  echo "  -> templates/.../telefon_tab.html"
  cp "${INCOMING}/templates/abpe_crm/tabs/telefon_tab.html" "${TEMPLATES}/tabs/telefon_tab.html"
fi

if [[ -x "${ARCHIV}/backup_restore.py" ]]; then
  echo "Backup..."
  NOTE="${NOTE:-vor telefon-stats-i18n}"
  for rel in \
    apps/abpe_crm/static/abpe_crm/js/mod-crm-pbx.js \
    apps/abpe_crm/static/abpe_crm/i18n/de/modules/crm_telefon/crm_telefon.json \
    apps/abpe_crm/templates/abpe_crm/tabs/telefon_tab.html; do
    if [[ -f "${BACKEND}/${rel}" ]]; then
      python3 "${ARCHIV}/backup_restore.py" -save "${rel}" -m "${NOTE}" || true
    fi
  done
fi

echo "Done. Run i18n_translator.py for other langs, then collectstatic + restart."
