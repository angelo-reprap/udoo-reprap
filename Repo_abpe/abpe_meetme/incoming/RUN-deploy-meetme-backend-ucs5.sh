#!/usr/bin/env bash
# MeetMe + Scheduler Backend: Git incoming/ → Live (ucs5)
#
#   cd /mnt/public/udoo-reprap && git pull
#   bash Repo_abpe/abpe_meetme/incoming/RUN-deploy-meetme-backend-ucs5.sh
#   cd /opt/abpe/backend && python manage.py migrate abpe_meetme --noinput
#   supervisorctl restart abpe-django abpe-scheduler-loop abpe-celery
#
# Nur anzeigen:
#   DRY_RUN=1 bash Repo_abpe/abpe_meetme/incoming/RUN-deploy-meetme-backend-ucs5.sh

set -euo pipefail

BACKEND="${ABPE_BACKEND:-/opt/abpe/backend}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# incoming/ → abpe_meetme/ → Repo_abpe/ → repo-root
REPO="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
DRY_RUN="${DRY_RUN:-0}"

echo "Repo:    $REPO"
echo "Backend: $BACKEND"
echo ""

deploy_app() {
  local app="$1"
  local src="${REPO}/Repo_abpe/${app}/incoming"
  local dest="${BACKEND}/apps/${app}"

  if [[ ! -d "$src" ]]; then
    echo "FEHLER: Quelle fehlt: $src" >&2
    echo "  → git pull ausführen (Branch cursor/meetme-backend-export-bf44)" >&2
    exit 1
  fi

  echo "--- Deploy $app ---"
  echo "  von: $src"
  echo "  nach: $dest"

  if [[ "$DRY_RUN" == "1" ]]; then
    rsync -ani --include '*/' --include '*.py' --exclude '*' "$src/" "$dest/" | grep -E '^[<>ch*]' || echo "GLEICH $app"
    return 0
  fi

  rsync -av --exclude '__pycache__/' --exclude '*.pyc' \
    --include '*/' --include '*.py' --exclude '*' \
    "$src/" "$dest/"
  echo "OK: $app deployed"
}

deploy_app abpe_meetme
deploy_app abpe_scheduler

echo ""
echo "=== Verifikation ==="
if grep -q "_mm_send_reminder_delivery" "${BACKEND}/apps/abpe_meetme/views.py" 2>/dev/null; then
  echo "OK: AUTO-Versand-Fix ist auf Live (_mm_send_reminder_delivery gefunden)"
  grep -n "_mm_send_reminder_delivery" "${BACKEND}/apps/abpe_meetme/views.py" | head -3
else
  echo "FEHLER: Fix NICHT auf Live!" >&2
  echo "  Git-Stand prüfen: grep _mm_send_reminder_delivery ${REPO}/Repo_abpe/abpe_meetme/incoming/views.py" >&2
  exit 1
fi

echo ""
echo "Fertig. Danach:"
echo "  cd $BACKEND && python manage.py migrate abpe_meetme --noinput"
echo "  supervisorctl restart abpe-django abpe-scheduler-loop abpe-celery"
