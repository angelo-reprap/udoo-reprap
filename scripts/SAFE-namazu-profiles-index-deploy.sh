#!/usr/bin/env bash
# Deploy: namazu_profiles_index (Command + Webhook-Handler + register_scheduler_jobs)
# auf Live-Shaduler, dann Job registrieren. Optional Catch-up Full-Index.
#
# ucs5:
#   cd /mnt/public/udoo-reprap
#   git pull origin cursor/namazu-schedule-windows-1532
#   bash scripts/SAFE-namazu-profiles-index-deploy.sh
#   # Catch-up einmal (nur wenn Index leer/alt):
#   FULL=1 bash scripts/SAFE-namazu-profiles-index-deploy.sh
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
LIVE_SH="${LIVE_SH:-/opt/abpe/backend/apps/abpe_shaduler}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
FULL="${FULL:-0}"
REGISTER="${REGISTER:-1}"
TS=$(date +%Y%m%d-%H%M%S)

cd "$REPO"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate

SRC="$REPO/Repo_abpe/abpe_shaduler/incoming"
if [[ ! -d "$SRC" ]]; then
  echo "FAIL: $SRC fehlt"
  exit 1
fi
if [[ ! -d "$LIVE_SH" ]]; then
  echo "FAIL: $LIVE_SH fehlt"
  exit 1
fi

mkdir -p "$LIVE_SH/management/commands"
for f in \
  management/commands/index_namazu_profiles.py \
  management/commands/register_scheduler_jobs.py \
  tasks.py
do
  if [[ -f "$LIVE_SH/$f" ]]; then
    cp -a "$LIVE_SH/$f" "$LIVE_SH/${f}.bak-namazu-$TS"
  fi
  mkdir -p "$(dirname "$LIVE_SH/$f")"
  cp -a "$SRC/$f" "$LIVE_SH/$f"
  echo "OK deploy $f"
done

find "$LIVE_SH" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "$LIVE_SH" -name '*.pyc' -delete 2>/dev/null || true

cd "$BACKEND"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"

if [[ "$REGISTER" == "1" ]]; then
  echo "── register_scheduler_jobs ──"
  python3 manage.py register_scheduler_jobs
fi

if [[ "$FULL" == "1" ]]; then
  echo "── FULL index_namazu_profiles (kann Minuten dauern) ──"
  python3 manage.py index_namazu_profiles --full
else
  echo "── Probe dry-run (20) ──"
  python3 manage.py index_namazu_profiles --dry-run --limit 20 || true
  echo
  echo "Catch-up: FULL=1 bash scripts/SAFE-namazu-profiles-index-deploy.sh"
  echo "Oder inkrementell: python3 manage.py index_namazu_profiles --incremental --since-hours 168"
fi

echo
echo "Health: bash scripts/CHECK-matching-index-health.sh"
echo "Erwartung: Jobs namazu_profiles_index + _22 + _03; max_indexed_at von abpe_namazu_profiles frisch nach FULL"
echo "Fenster: Mo–Fr 08–19 alle 10 Min (Europe/Berlin); täglich 22:00 und 03:00"
