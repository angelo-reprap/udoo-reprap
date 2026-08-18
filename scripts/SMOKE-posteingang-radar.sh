#!/usr/bin/env bash
# Smoke-Check Posteingang / Radar (nur lesen, kein Write).
#
#   bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/SMOKE-posteingang-radar.sh)
#
set -euo pipefail
BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"
cd "$BACKEND"

echo "======== SMOKE Posteingang/Radar $(date -Iseconds) ========"

echo "=== Prozesse ==="
supervisorctl status abpe-django abpe-celery abpe-scheduler-loop 2>/dev/null || true
ss -lntp 2>/dev/null | grep -E ':8000\s' || true

echo
echo "=== Scheduler Jobs (127.0.0.1?) ==="
"$PYBIN" - <<'PY' 2>/dev/null | grep -E '^(SCHEDULER|SHADULER|  )' || true
import os, django, requests
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from django.conf import settings
api = getattr(settings, 'SCHEDULER_API_BASE_URL', '')
cb = getattr(settings, 'SHADULER_CALLBACK_BASE_URL', '')
print('SCHEDULER_API_BASE_URL=', api)
print('SHADULER_CALLBACK_BASE_URL=', cb or '(default/normalize)')
tok = getattr(settings, 'SCHEDULER_SERVICE_TOKEN', '') or ''
h = {'Authorization': f'Token {tok}'} if tok else {}
base = (api or 'http://127.0.0.1:8000/scheduler/api').rstrip('/')
# normalize localhost display
base = base.replace('://localhost:', '://127.0.0.1:')
try:
    r = requests.get(base + '/jobs/', headers=h, timeout=8)
    print('jobs HTTP', r.status_code)
    data = r.json() if r.ok else {}
    jobs = data if isinstance(data, list) else (data.get('results') or data.get('jobs') or [])
    keys = ('radar_poll', 'inbox_poll', 'email_index', 'radar_berater_index', 'prozess_tick')
    for j in jobs:
        if not isinstance(j, dict):
            continue
        k = j.get('job_key') or j.get('key') or ''
        if k in keys or any(x in str(j.get('callback_url') or '') for x in keys):
            print(f"  {k} status={j.get('status')} cb={str(j.get('callback_url') or '')[:90]}")
except Exception as e:
    print('jobs ERR', type(e).__name__, e)
PY

echo
echo "=== Inbox Probe ==="
"$PYBIN" manage.py shaduler_inbox_probe --fetch --limit 3 2>/dev/null \
  | grep -E 'source=|newest|● |bad_future|reachable|count=' || true

echo
echo "=== Radar Berater ES ==="
"$PYBIN" - <<'PY'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from apps.abpe_shaduler.services import radar_berater_index as idx
from apps.abpe_shaduler.services import radar_berater_service as rbs
st = idx.index_stats(sample=False)
pack = idx.search(q='', days=None, limit=2)
data = rbs.list_berater(q='', days=0, status='neu', limit=2, available_only=True)
print('index', st.get('index'), 'count', st.get('count'), 'ok', st.get('ok'))
print('search error', (pack or {}).get('error'), 'total', (pack or {}).get('total'))
print('list_source', data.get('list_source'), 'es_total', data.get('es_total'),
      'fallback', (data.get('es_info') or {}).get('fallback'),
      'search_error', (data.get('es_info') or {}).get('search_error'))
PY

echo
echo "=== Radar Anfragen (kurz) ==="
"$PYBIN" - <<'PY'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
try:
    from apps.abpe_shaduler.models import RadarItem
    n = RadarItem.objects.count()
    print('RadarItem count', n)
except Exception as e:
    try:
        from apps.abpe_shaduler.models import RadarAnfrageItem
        print('RadarAnfrageItem', RadarAnfrageItem.objects.count())
    except Exception as e2:
        print('radar models', e, '|', e2)
PY

echo
echo "Browser Ctrl+F5: Posteingang · Radar Anfragen · Radar Berater"
echo "Erwartet Berater-Hinweis: Liste ES (ohne ES-Fehler)"
