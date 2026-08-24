#!/usr/bin/env bash
# Probe: ein Matching-Index für Pipeline + Wild-Ogo (Date-Segmente + Weight).
#
# ucs5:
#   cd /mnt/public/udoo-reprap
#   git fetch && git checkout cursor/matching-unified-index-probe-1532 && git pull
#   bash scripts/SAFE-matching-unified-probe-deploy.sh   # Code → Live-Shaduler
#   bash scripts/PROBE-matching-unified-index.sh         # DRY
#   EXECUTE=1 bash scripts/PROBE-matching-unified-index.sh
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
PIPELINE="${PIPELINE:-5}"
WILD="${WILD:-5}"
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
  --pipeline "$PIPELINE"
  --wild "$WILD"
  --skills "$SKILLS"
  --index "$INDEX"
)
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
