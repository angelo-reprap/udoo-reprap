#!/usr/bin/env bash
# Probe: Contact-zentrierter Matching-Gewichtungs-Index
# (CV-Pipeline-Weights ODER Wild aus ogo/*_profil.c — 1 Doc pro Contact-ID).
#
# ucs5:
#   cd /mnt/public/udoo-reprap
#   git pull origin cursor/matching-contact-weight-index-1532
#   bash scripts/SAFE-matching-unified-probe-deploy.sh
#   bash scripts/PROBE-matching-unified-index.sh              # DRY, 20 Contacts
#   EXECUTE=1 CONTACTS=40 bash scripts/PROBE-matching-unified-index.sh
#   # Einzelne Prüfschleife:
#   CONTACT_ID=<crm-uuid> bash scripts/PROBE-matching-unified-index.sh
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
CONTACTS="${CONTACTS:-20}"
CONTACT_ID="${CONTACT_ID:-}"
SKILLS="${SKILLS:-Java,Python,Perl,Django,Spring,Kubernetes,Docker,AWS,SAP,SQL,Linux}"
INDEX="${INDEX:-abpe_matching_profiles_probe}"
EXECUTE="${EXECUTE:-0}"
SEARCH="${SEARCH:-1}"

cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"

ARGS=(
  probe_matching_unified_index
  --skills "$SKILLS"
  --index "$INDEX"
)
if [[ -n "$CONTACT_ID" ]]; then
  ARGS+=(--contact-id "$CONTACT_ID")
else
  ARGS+=(--contacts "$CONTACTS")
fi

if [[ "$EXECUTE" == "1" ]]; then
  ARGS+=(--execute --recreate)
  if [[ "$SEARCH" == "1" ]]; then
    ARGS+=(--search)
  fi
else
  ARGS+=(--dry-run)
fi

echo "→ python manage.py ${ARGS[*]}"
python3 manage.py "${ARGS[@]}"
