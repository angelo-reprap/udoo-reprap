#!/usr/bin/env bash
# Live ucs5: SCHEDULER localhost → 127.0.0.1
# Live-Pfade (NICHT Repo-incoming/):
#   apps/abpe_shaduler/scheduler_client.py
#   abpe_backend/settings/base.py  (SCHEDULER_API_BASE_URL)
#
# Default = CHECK only. APPLY=1 schreibt erst nach backup_restore -save.
#
#   bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/FIX-scheduler-url-127.sh)
#   APPLY=1 bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/FIX-scheduler-url-127.sh)
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"
APPLY="${APPLY:-0}"
BR="$BACKEND/apps/abpe_ui/backup_restore.py"
BASE_PY="$BACKEND/abpe_backend/settings/base.py"
CLIENT="$BACKEND/apps/abpe_shaduler/scheduler_client.py"
REPO_CLIENT_REF="origin/cursor/posteingang-radar-fix-1532:Repo_abpe/abpe_shaduler/incoming/scheduler_client.py"

cd "$BACKEND"

echo "======== FIX scheduler URL localhost→127.0.0.1 APPLY=$APPLY ========"
echo "Regel: CHECK Live → backup_restore -save → dann schreiben"
echo

echo "=== 1) CHECK Live-Dateien ==="
for f in "$BASE_PY" "$CLIENT"; do
  if [[ -f "$f" ]]; then
    echo "OK  $f"
    ls -la "$f"
  else
    echo "FEHLT  $f"
  fi
done

echo
echo "--- base.py Scheduler-Zeilen ---"
if [[ -f "$BASE_PY" ]]; then
  grep -nE 'SCHEDULER_API_BASE_URL|SHADULER_CALLBACK|MEETME_CALLBACK|localhost:8000/(scheduler|shaduler|meetme)' "$BASE_PY" || true
fi

echo
echo "--- scheduler_client.py URL-Defaults ---"
if [[ -f "$CLIENT" ]]; then
  grep -nE 'localhost|127\.0\.0\.1|_base_url|_callback|_normalize' "$CLIENT" | head -40 || true
fi

echo
echo "=== 2) Django effektiv ==="
"$PYBIN" - <<'PY'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from django.conf import settings
for name in ('SCHEDULER_API_BASE_URL', 'SHADULER_CALLBACK_BASE_URL', 'MEETME_CALLBACK_BASE_URL'):
    if hasattr(settings, name):
        print(f'  {name} = {getattr(settings, name)!r}')
    else:
        print(f'  {name} = (nicht gesetzt)')
PY

echo
echo "Empfohlen nach Patch:"
echo "  SCHEDULER_API_BASE_URL = 'http://127.0.0.1:8000/scheduler/api'"
echo "  SHADULER_CALLBACK_BASE_URL = 'http://127.0.0.1:8000/shaduler/api'"
echo "  (MEETME_CALLBACK optional gleiches Muster — hier unberührt)"

if [[ "$APPLY" != "1" ]]; then
  echo
  echo "DRY-RUN / CHECK only. Zum Schreiben:"
  echo "  APPLY=1 bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/FIX-scheduler-url-127.sh)"
  exit 0
fi

# --- APPLY ---
if [[ ! -f "$BR" ]]; then
  echo "FAIL: backup_restore fehlt: $BR — Abbruch (kein Write ohne Archiv)"
  exit 2
fi
if [[ ! -f "$BASE_PY" || ! -f "$CLIENT" ]]; then
  echo "FAIL: Ziel-Dateien fehlen — Abbruch"
  exit 2
fi

echo
echo "=== 3) backup_restore -save ==="
"$PYBIN" "$BR" -save "abpe_backend/settings/base.py" \
  -m "schedurl: vor localhost→127.0.0.1 SCHEDULER_API"
"$PYBIN" "$BR" -save "apps/abpe_shaduler/scheduler_client.py" \
  -m "schedurl: vor localhost→127.0.0.1 client normalize"

echo
echo "=== 4) Write: base.py nur SCHEDULER_API_BASE_URL ==="
# Nur diese eine Zeile; MEETME unberührt; SHADULER_CALLBACK hinzufügen falls fehlt
if grep -q "SCHEDULER_API_BASE_URL = 'http://localhost:8000/scheduler/api'" "$BASE_PY"; then
  sed -i "s|SCHEDULER_API_BASE_URL = 'http://localhost:8000/scheduler/api'|SCHEDULER_API_BASE_URL = 'http://127.0.0.1:8000/scheduler/api'|" "$BASE_PY"
  echo "OK base.py SCHEDULER_API → 127.0.0.1"
elif grep -q "SCHEDULER_API_BASE_URL = 'http://127.0.0.1:8000/scheduler/api'" "$BASE_PY"; then
  echo "OK base.py SCHEDULER_API schon 127.0.0.1"
else
  echo "WARN: SCHEDULER_API_BASE_URL Zeile unerwartet — manuell prüfen:"
  grep -n 'SCHEDULER_API_BASE_URL' "$BASE_PY" || true
fi

if ! grep -q 'SHADULER_CALLBACK_BASE_URL' "$BASE_PY"; then
  # Direkt nach SCHEDULER_API einfügen
  sed -i "/SCHEDULER_API_BASE_URL = /a SHADULER_CALLBACK_BASE_URL = 'http://127.0.0.1:8000/shaduler/api'" "$BASE_PY"
  echo "OK base.py SHADULER_CALLBACK_BASE_URL ergänzt"
else
  sed -i "s|SHADULER_CALLBACK_BASE_URL = 'http://localhost:8000/shaduler/api'|SHADULER_CALLBACK_BASE_URL = 'http://127.0.0.1:8000/shaduler/api'|" "$BASE_PY" || true
  echo "OK base.py SHADULER_CALLBACK geprüft/angepasst"
fi

echo
echo "=== 5) Write: scheduler_client.py aus Repo (normalize) ==="
# CHECK: Repo-Ref muss fetchbar sein
if ! git -C /mnt/public/udoo-reprap show "$REPO_CLIENT_REF" >/dev/null 2>&1; then
  echo "Repo-Ref fehlt — fetch + Defaults per sed"
  sed -i \
    -e "s|http://localhost:8000/scheduler/api|http://127.0.0.1:8000/scheduler/api|g" \
    -e "s|http://localhost:8000/shaduler/api|http://127.0.0.1:8000/shaduler/api|g" \
    "$CLIENT"
else
  git -C /mnt/public/udoo-reprap show "$REPO_CLIENT_REF" > "$CLIENT"
fi
echo "OK client geschrieben"
grep -nE '127\.0\.0\.1|localhost|_normalize' "$CLIENT" | head -20 || true

echo
echo "=== 6) register_scheduler_jobs ==="
"$PYBIN" manage.py register_scheduler_jobs
echo
echo "Erfolg = Callbacks mit http://127.0.0.1:8000/shaduler/..."
echo "Falls Django Settings cached: supervisorctl restart abpe-django"
