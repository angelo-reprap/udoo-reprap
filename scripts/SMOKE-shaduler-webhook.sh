#!/usr/bin/env bash
# Manueller Webhook-Smoke (inbox-poll) — unabhängig vom CHECK-Skript.
#
# Auf ucs5 (zuerst fetchen!):
#   cd /mnt/public/udoo-reprap && git fetch origin cursor/abpe-shaduler-scaffold-7f07
#   bash <(git show origin/cursor/abpe-shaduler-scaffold-7f07:scripts/SMOKE-shaduler-webhook.sh)
set -euo pipefail
BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"
export SHADULER_SMOKE_URL="${URL:-http://127.0.0.1:8000/shaduler/api/webhook/inbox-poll/}"

cd "$BACKEND"
exec "$PYBIN" - <<'PY'
import os, django, urllib.request, urllib.error
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from django.conf import settings
from apps.abpe_shaduler import tasks

print('handlers:', sorted(set(tasks.JOB_HANDLERS)))
tok = getattr(settings, 'SCHEDULER_SERVICE_TOKEN', '') or ''
if not tok:
    print('FAIL: SCHEDULER_SERVICE_TOKEN leer')
    raise SystemExit(1)
url = os.environ['SHADULER_SMOKE_URL']
req = urllib.request.Request(
    url,
    data=b'{"job":"inbox_poll"}',
    headers={'Authorization': f'Token {tok}', 'Content-Type': 'application/json'},
    method='POST',
)
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        print(f'OK HTTP {r.status}:', r.read()[:400])
except urllib.error.HTTPError as e:
    print(f'FAIL HTTP {e.code}:', e.read()[:300])
    if e.code == 401:
        print('→ Token angleichen (wie MeetMe): SCHEDULER_SERVICE_TOKEN')
    raise SystemExit(1)
PY
