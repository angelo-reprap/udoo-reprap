#!/usr/bin/env bash
# Deploy CRM detail-panel + E-Mail Kampagne i18n
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
INCOMING="$(cd "$(dirname "$0")" && pwd)"
STATIC="${BACKEND}/apps/abpe_crm/static/abpe_crm"
TEMPLATES="${BACKEND}/apps/abpe_crm/templates/abpe_crm"
ARCHIV="${BACKEND}/Archiv"

echo "=== CRM i18n Deploy (Detail + Kampagne) ==="
echo "Source: ${INCOMING}"
echo "Target: ${STATIC}"

for f in mod-crm.js mod-crm-kunden.js mod-crm-berater.js mod-crm-edit.js mod-crm-kampagne.js; do
  src="${INCOMING}/${f}"
  if [[ -f "${INCOMING}/js/${f}" ]]; then src="${INCOMING}/js/${f}"; fi
  echo "  -> js/${f}"
  cp "${src}" "${STATIC}/js/${f}"
done

echo "  -> i18n/de/crm.json"
cp "${INCOMING}/i18n/de/crm.json" "${STATIC}/i18n/de/crm.json"

if [[ -d "${TEMPLATES}/components" ]]; then
  echo "  -> templates/.../header.html"
  cp "${INCOMING}/templates/abpe_crm/components/header.html" "${TEMPLATES}/components/header.html"
fi

if [[ -d "${TEMPLATES}/tabs" ]]; then
  echo "  -> templates/.../emails_tab.html"
  cp "${INCOMING}/templates/abpe_crm/tabs/emails_tab.html" "${TEMPLATES}/tabs/emails_tab.html"
fi

if [[ -x "${ARCHIV}/backup_restore.py" ]]; then
  echo "Backup..."
  NOTE="${NOTE:-vor crm-i18n-deploy}"
  for rel in \
    apps/abpe_crm/static/abpe_crm/js/mod-crm.js \
    apps/abpe_crm/static/abpe_crm/js/mod-crm-kunden.js \
    apps/abpe_crm/static/abpe_crm/js/mod-crm-berater.js \
    apps/abpe_crm/static/abpe_crm/js/mod-crm-edit.js \
    apps/abpe_crm/static/abpe_crm/js/mod-crm-kampagne.js \
    apps/abpe_crm/static/abpe_crm/i18n/de/crm.json \
    apps/abpe_crm/templates/abpe_crm/tabs/emails_tab.html; do
    if [[ -f "${BACKEND}/${rel}" ]]; then
      python3 "${ARCHIV}/backup_restore.py" -save "${rel}" -m "${NOTE}" || true
    fi
  done
fi

echo "Done. Run i18n_translator.py for other langs, then collectstatic + restart."
