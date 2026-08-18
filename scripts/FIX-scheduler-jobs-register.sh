#!/usr/bin/env bash
# Nach pe-SYNC: Scheduler-API-URL prüfen + Jobs registrieren + Inbox-Probe.
# Kein Datei-Overwrite.
#
#   bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/FIX-scheduler-jobs-register.sh)
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"
cd "$BACKEND"

echo "======== FIX scheduler jobs $(date -Iseconds) ========"

echo "=== 1) Settings / Ports ==="
"$PYBIN" - <<'PY'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from django.conf import settings
api = getattr(settings, 'SCHEDULER_API_BASE_URL', None)
cb = getattr(settings, 'SHADULER_CALLBACK_BASE_URL', None)
tok = getattr(settings, 'SCHEDULER_SERVICE_TOKEN', '') or ''
print('SCHEDULER_API_BASE_URL     =', api or '(default localhost:8000/scheduler/api)')
print('SHADULER_CALLBACK_BASE_URL =', cb or '(default localhost:8000/shaduler/api)')
print('SCHEDULER_SERVICE_TOKEN    =', ('SET len=%d' % len(tok)) if tok else 'LEER')
PY

echo
echo "=== 2) Was lauscht (django/gunicorn) ==="
ss -lntp 2>/dev/null | grep -E ':(8000|8080|80|443)\s' || netstat -lntp 2>/dev/null | grep -E ':(8000|8080)' || true
supervisorctl status abpe-django abpe-celery abpe-scheduler-loop 2>/dev/null || true

echo
echo "=== 3) Kandidaten für API-Base testen ==="
"$PYBIN" - <<'PY'
import os, django, requests
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from django.conf import settings

tok = getattr(settings, 'SCHEDULER_SERVICE_TOKEN', '') or ''
headers = {'Authorization': f'Token {tok}', 'Content-Type': 'application/json'} if tok else {}

# Reihenfolge: 127.0.0.1 vor localhost (IPv6/Timeout-Falle auf ucs5)
candidates = [
    'http://127.0.0.1:8000/scheduler/api',
    'http://localhost:8000/scheduler/api',
    'http://127.0.0.1:8080/scheduler/api',
    'http://127.0.0.1/scheduler/api',
    'http://ucs5.win.abcona.info/scheduler/api',
    'https://abpe.win.abcona.info/scheduler/api',
]
cur = getattr(settings, 'SCHEDULER_API_BASE_URL', None)
if cur:
    c = cur.rstrip('/')
    if c not in candidates:
        candidates.insert(0, c)

ok = []
for base in candidates:
    url = base + '/jobs/'
    try:
        r = requests.get(url, headers=headers, timeout=3)
        print(f'  {r.status_code:3d}  {url}')
        if r.status_code in (200, 401, 403):  # erreichbar
            ok.append(base)
    except Exception as e:
        print(f'  ERR  {url}  ({type(e).__name__}: {e})')

print()
if ok:
    # Preferiere 127.0.0.1 über localhost auch wenn beide 200
    preferred = next((b for b in ok if '127.0.0.1' in b), ok[0])
    print('ERREICHBAR (bevorzugt):', preferred)
    cur_api = (getattr(settings, 'SCHEDULER_API_BASE_URL', None) or '').rstrip('/')
    if 'localhost' in cur_api and '127.0.0.1' in preferred:
        print('WARN: Settings nutzen localhost — flaky. Umstellen:')
        print('  bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/FIX-scheduler-url-127.sh)')
        print('  APPLY=1 bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/FIX-scheduler-url-127.sh)')
    print('Empfohlen in Live-Settings:')
    print(f"  SCHEDULER_API_BASE_URL = '{preferred}'")
    host = preferred.split('/scheduler')[0]
    print(f"  SHADULER_CALLBACK_BASE_URL = '{host}/shaduler/api'")
else:
    print('KEINE Scheduler-API erreichbar — abpe-django Port prüfen / nginx upstream')
PY

echo
echo "=== 4) register_scheduler_jobs (nutzt Settings) ==="
if "$PYBIN" manage.py register_scheduler_jobs; then
  echo "OK register"
else
  echo "FAIL register — Settings-URL korrigieren, dann erneut"
fi

echo
echo "=== 5) Inbox Probe ==="
"$PYBIN" manage.py shaduler_inbox_probe --fetch --limit 5 2>/dev/null \
  || "$PYBIN" manage.py shaduler_inbox_probe --limit 5 || true

echo
echo "=== 6) Optional: email_index Webhook einmal manuell ==="
echo "(nur wenn Token+Callback stimmen — siehe SMOKE-shaduler-webhook.sh)"
