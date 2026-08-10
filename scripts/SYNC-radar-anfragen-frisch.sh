#!/usr/bin/env bash
# ⚠ TEIL-SYNC: kann „Neue Aufgabe“ / andere Features überschreiben!
# Bevorzugt: scripts/SYNC-shaduler-all-in-one.sh (Branch cursor/shaduler-all-in-one-7f07)
# Radar Anfragen frisch halten: Shaduler + UI + scheduler-loop + Jobs.
# Basiert auf Matching-Sync, Branch = radar-anfragen-frisch.
#
# ucs5:
#   cd /mnt/public/udoo-reprap && git fetch origin cursor/shaduler-all-in-one-7f07
#   bash <(git show origin/cursor/shaduler-all-in-one-7f07:scripts/SYNC-radar-anfragen-frisch.sh)
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
export BRANCH="${BRANCH:-origin/cursor/shaduler-all-in-one-7f07}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"

cd "$REPO"
git fetch origin cursor/shaduler-all-in-one-7f07 || true

# Wiederverwendet Matching-Sync (gleiche Artefakte, anderer Branch via BRANCH=)
bash <(git show "$BRANCH:scripts/SYNC-matching-ki-anfrage-wizard.sh")

echo
echo "=== Jobs neu registrieren (radar_poll + email_index alle 3 Min, async) ==="
cd "$BACKEND"
"$PYBIN" manage.py register_scheduler_jobs

echo
echo "=== Scheduler-Loop dauerhaft RUNNING ==="
bash <(git show "$BRANCH:scripts/ENSURE-abpe-scheduler-loop.sh")

echo
echo "=== Catch-up Radar (einmal Live-Poll) ==="
"$PYBIN" manage.py radar_dedupe_sources --apply 2>/dev/null || true
"$PYBIN" manage.py radar_fix_published_dates --apply 2>/dev/null || true
"$PYBIN" manage.py radar_run_once --pages 2 --days 2 2>/dev/null \
  || "$PYBIN" - <<'PY'
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from apps.abpe_shaduler.services import radar_fetcher
print(radar_fetcher.poll_once(pages=2, today_only=True, recent_days=2))
PY

echo
supervisorctl restart abpe-django abpe-celery
sleep 2
supervisorctl status abpe-django abpe-celery abpe-scheduler-loop
echo
echo "OK — Radar: alle 3 Min Poll (Celery) + UI Soft-Poll 60s / Live 3 Min"
echo "Browser: Ctrl+F5 auf Radar — Anfragen"
