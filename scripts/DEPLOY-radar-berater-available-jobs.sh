#!/usr/bin/env bash
# Deploy + register: Radar-Berater „Verfügbare“-Jobs (Gulp/FL).
# CHECK Live → Archiv → Write → register_scheduler_jobs → optional Sync-Probe.
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/posteingang-radar-fix-1532
#   bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/DEPLOY-radar-berater-available-jobs.sh)
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
LIVE="${LIVE_SHADULER:-$BACKEND/apps/abpe_shaduler}"
REF="${REF:-origin/cursor/posteingang-radar-fix-1532}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"
APPLY="${APPLY:-0}"
SYNC_NOW="${SYNC_NOW:-0}"

cd "$REPO"
git fetch origin cursor/posteingang-radar-fix-1532

echo "======== DEPLOY radar berater available jobs APPLY=$APPLY ========"

FILES=(
  tasks.py
  management/commands/register_scheduler_jobs.py
)

echo "=== CHECK Live vs Branch ==="
for f in "${FILES[@]}"; do
  src="$REPO/Repo_abpe/abpe_shaduler/incoming/$f"
  # prefer git show
  live="$LIVE/$f"
  echo "--- $f ---"
  if [[ -f "$live" ]]; then
    git -C "$REPO" show "$REF:Repo_abpe/abpe_shaduler/incoming/$f" > /tmp/_radar_new_"$(basename "$f")"
    if cmp -s "$live" /tmp/_radar_new_"$(basename "$f")"; then
      echo "SAME"
    else
      echo "DIFF (Live ≠ Branch)"
      diff -u "$live" /tmp/_radar_new_"$(basename "$f")" | head -40 || true
    fi
  else
    echo "MISSING Live: $live"
  fi
done

if [[ "$APPLY" != "1" ]]; then
  echo
  echo "DRY-RUN. Zum Schreiben:"
  echo "  APPLY=1 bash <(git show $REF:scripts/DEPLOY-radar-berater-available-jobs.sh)"
  echo "  APPLY=1 SYNC_NOW=1 bash <(git show $REF:scripts/DEPLOY-radar-berater-available-jobs.sh)"
  exit 0
fi

echo
echo "=== Archiv ==="
cd "$BACKEND"
for f in "${FILES[@]}"; do
  "$PYBIN" apps/abpe_ui/backup_restore.py -save "apps/abpe_shaduler/$f" \
    -m "vor: radar berater available jobs" || true
done

echo
echo "=== Write ==="
for f in "${FILES[@]}"; do
  mkdir -p "$(dirname "$LIVE/$f")"
  git -C "$REPO" show "$REF:Repo_abpe/abpe_shaduler/incoming/$f" > "$LIVE/$f"
  echo "OK → $LIVE/$f"
done

echo
echo "=== register_scheduler_jobs ==="
"$PYBIN" manage.py register_scheduler_jobs

echo
echo "=== verify jobs ==="
"$PYBIN" - <<'PY'
import os, django, requests, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from django.conf import settings
api = (getattr(settings, 'SCHEDULER_API_BASE_URL', '') or 'http://127.0.0.1:8000/scheduler/api').rstrip('/')
api = api.replace('://localhost:', '://127.0.0.1:')
tok = getattr(settings, 'SCHEDULER_SERVICE_TOKEN', '') or ''
h = {'Authorization': f'Token {tok}'} if tok else {}
r = requests.get(api + '/jobs/', headers=h, timeout=10)
jobs = r.json() if r.ok else {}
jobs = jobs if isinstance(jobs, list) else (jobs.get('results') or jobs.get('jobs') or [])
want = ('radar_berater_gulp_available', 'radar_berater_fl_available', 'radar_berater_index')
for j in jobs:
    if not isinstance(j, dict):
        continue
    k = j.get('job_key') or j.get('key') or ''
    if k in want or any(w in str(k) for w in want):
        print(f"  {k} status={j.get('status')} next={j.get('next_run_at') or j.get('next_run')} cb={str(j.get('callback_url') or '')[:90]}")
PY

if [[ "$SYNC_NOW" == "1" ]]; then
  echo
  echo "=== SYNC_NOW gulp available ==="
  "$PYBIN" manage.py radar_berater_gulp_available --limit 40 --pages 2
  echo
  echo "=== SYNC_NOW fl available ==="
  "$PYBIN" manage.py radar_berater_fl_available --limit 36 --pages 2 || true
fi

echo
echo "Fertig. Browser Ctrl+F5 Radar · Berater — Top sollte frische Verfügbare sein."
echo "Celery ggf. neu laden: supervisorctl restart abpe-celery"
