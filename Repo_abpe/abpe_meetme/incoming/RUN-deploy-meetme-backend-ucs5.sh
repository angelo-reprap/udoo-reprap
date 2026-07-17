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
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
DRY_RUN="${DRY_RUN:-0}"

deploy_app() {
  local app="$1"
  local src="${REPO}/Repo_abpe/${app}/incoming"
  local dest="${BACKEND}/apps/${app}"

  if [[ ! -d "$src" ]]; then
    echo "SKIP  fehlt: $src"
    return 0
  fi

  echo "--- Deploy $app ---"
  if [[ "$DRY_RUN" == "1" ]]; then
    rsync -ani --include '*/' --include '*.py' --exclude '*' "$src/" "$dest/" | grep -E '^[<>ch*]' || echo "GLEICH $app"
    return 0
  fi

  rsync -a --exclude '__pycache__/' --exclude '*.pyc' \
    --include '*/' --include '*.py' --exclude '*' \
    "$src/" "$dest/"
  echo "OK: $src -> $dest"
}

deploy_app abpe_meetme
deploy_app abpe_scheduler

echo ""
echo "Fertig. Danach:"
echo "  cd $BACKEND && python manage.py migrate abpe_meetme --noinput"
echo "  supervisorctl restart abpe-django abpe-scheduler-loop abpe-celery"
