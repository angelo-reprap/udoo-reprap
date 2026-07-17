#!/usr/bin/env bash
# EDMS: Firma-Dokumente inkl. Ansprechpartner (Rollup)
#
#   cd /mnt/public/udoo-reprap && git pull
#   bash Repo_abpe/abpe_edms/incoming/RUN-deploy-edms-account-rollup-ucs5.sh
#   supervisorctl restart abpe-django
#
# Behebt: adegna GmbH zeigt nur info@adegna.com — nicht matthias.patzer@adegna.com
# Fix: Akte + Mails + Kunden-Dokumente = Firma + alle Ansprechpartner

set -euo pipefail

REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
BACKEND="${ABPE_BACKEND:-/opt/abpe/backend}"

echo "Repo:    $REPO"
echo "Backend: $BACKEND"
echo ""

python3 "${REPO}/Repo_abpe/abpe_edms/incoming/patches/apply_account_doc_rollup.py"

echo ""
echo "=== Verifikation ==="
if grep -q "document_filter_for_entity" "${BACKEND}/apps/abpe_edms/views.py" 2>/dev/null; then
  echo "OK: api_akte Rollup in edms/views.py"
else
  echo "FEHLER: Rollup nicht in edms/views.py" >&2
  exit 1
fi
if grep -q "email_addresses_for_crm_ids" "${BACKEND}/apps/abpe_edms/views.py" 2>/dev/null; then
  echo "OK: api_person_mails Rollup in edms/views.py"
else
  echo "FEHLER: Mail-Rollup nicht in edms/views.py" >&2
  exit 1
fi
if [[ -f "${BACKEND}/apps/abpe_edms/owner_rollup.py" ]]; then
  echo "OK: owner_rollup.py auf Live"
else
  echo "FEHLER: owner_rollup.py fehlt" >&2
  exit 1
fi

echo ""
echo "Fertig. Test: /crm/dms/ → adegna GmbH → Akte sollte AP-Dokumente/Mails enthalten."
