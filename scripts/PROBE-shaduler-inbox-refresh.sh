#!/usr/bin/env bash
# Live-Diagnose: Posteingang Soft-Poll + ES-Indexer (ucs5, copy&paste)
#   bash <(git -C /mnt/public/udoo-reprap show origin/cursor/abpe-shaduler-scaffold-7f07:scripts/PROBE-shaduler-inbox-refresh.sh)
set -u
BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
STATICFILES="${STATICFILES:-/opt/abpe/backend/staticfiles}"

_has() { command -v "$1" >/dev/null 2>&1; }
_grep() {
  if _has rg; then rg "$@"
  else grep -E "$@"
  fi
}

echo "======== PROBE shaduler inbox refresh $(date -Iseconds) ========"
echo

echo "=== 1) Soft-Poll im App-Static? ==="
APP_JS="$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js"
if [[ -f "$APP_JS" ]]; then
  echo "OK file $APP_JS"
  echo "  mtime=$(stat -c %y "$APP_JS" 2>/dev/null || true)"
  if _grep -n "INBOX_POLL_MS|startInboxPoll|inboxIsBusy" "$APP_JS" >/dev/null; then
    echo "OK Soft-Poll in App-JS"
    _grep -n "INBOX_POLL_MS|startInboxPoll" "$APP_JS" | head -5
  else
    echo "FAIL: Soft-Poll-Strings fehlen in App-JS"
  fi
else
  echo "FAIL: $APP_JS fehlt"
fi
echo

echo "=== 2) Soft-Poll in STATIC_ROOT (Browser)? ==="
SF_JS="$STATICFILES/abpe_ui/js/mod/mod-shaduler.js"
if [[ -f "$SF_JS" ]]; then
  echo "OK file $SF_JS"
  echo "  mtime=$(stat -c %y "$SF_JS" 2>/dev/null || true)"
  if _grep -q "INBOX_POLL_MS|startInboxPoll" "$SF_JS"; then
    echo "OK Soft-Poll in staticfiles"
  else
    echo "FAIL: Soft-Poll FEHLT in staticfiles → SYNC/collectstatic"
  fi
else
  echo "WARN: $SF_JS fehlt"
fi
echo

echo "=== 3) Diff App vs Staticfiles ==="
if [[ -f "$APP_JS" && -f "$SF_JS" ]]; then
  if cmp -s "$APP_JS" "$SF_JS"; then
    echo "OK identisch"
  else
    echo "FAIL: unterschiedlich"
    diff -u "$SF_JS" "$APP_JS" | head -25 || true
  fi
fi
echo

echo "=== 4) Supervisor ==="
supervisorctl status abpe-django abpe-celery abpe-scheduler-loop 2>/dev/null \
  || supervisorctl status all 2>/dev/null | _grep 'abpe-(django|celery|scheduler)' || true
if supervisorctl status abpe-scheduler-loop 2>/dev/null | grep -q RUNNING; then
  echo "OK abpe-scheduler-loop RUNNING"
else
  echo "FAIL: abpe-scheduler-loop NICHT RUNNING — ohne Taktgeber kein email_index!"
  echo "  Fix: bash <(git -C /mnt/public/udoo-reprap show origin/cursor/posteingang-radar-fix-1532:scripts/ENSURE-abpe-scheduler-loop.sh)"
fi
echo

echo "=== 5) Celery Task ==="
cd "$BACKEND"
"$PYBIN" - <<'PY'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from apps.abpe_shaduler.tasks import email_index_run, JOB_HANDLERS
print('OK', getattr(email_index_run, 'name', email_index_run), 'delay=', hasattr(email_index_run, 'delay'))
print('OK handlers', sorted(k for k in JOB_HANDLERS if 'email' in k))
PY
echo

echo "=== 6) SchedulerJob email_index Runs ==="
"$PYBIN" - <<'PY'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from apps.abpe_scheduler.models import SchedulerJob, SchedulerJobRun
jobs = SchedulerJob.objects.filter(job_key='email_index').order_by('-id')[:2]
if not jobs:
    print('FAIL: kein email_index Job')
for j in jobs:
    print(f'JOB id={j.id} status={j.status} next={j.next_run_at}')
    print(f'  cb={j.callback_url}')
    print(f'  has_token_in_url={"token=" in (j.callback_url or "")}')
    print(f'  payload={j.payload}')
    for r in SchedulerJobRun.objects.filter(job=j).order_by('-id')[:5]:
        print(f'  RUN {r.id} {r.status} http={r.response_status} err={(r.error_message or "")[:80]!r} body={(r.response_body or "")[:120]!r}')
PY
echo

echo "=== 7) ES newest (probe) ==="
"$PYBIN" manage.py shaduler_inbox_probe --fetch --limit 3 2>/dev/null | _grep 'newest_date|count=|source=elasticsearch|● |reachable' \
  || "$PYBIN" manage.py shaduler_inbox_probe --fetch --limit 3 2>&1 | tail -25
echo

echo "=== 8) Webhook ohne Auth-Header (wie Scheduler) ==="
"$PYBIN" - <<'PY'
import os, django, json, time, urllib.request
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from django.conf import settings
from apps.abpe_shaduler import scheduler_client as sc
tok = getattr(settings, 'SCHEDULER_SERVICE_TOKEN', '') or ''
url = sc.build_callback_url('email-index')
print('callback_url=', url[:100] + ('…' if len(url) > 100 else ''))
print('has_token_in_url=', 'token=' in url)
body = json.dumps({'job': 'email_index', 'since_days': 1, 'folders': 'INBOX', 'incremental': True}).encode()
req = urllib.request.Request(url, data=body, method='POST', headers={'Content-Type': 'application/json'})
t0 = time.time()
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read().decode()
        print(f'HTTP {r.status} in {time.time()-t0:.2f}s (ohne Auth-Header)')
        print(raw[:400])
except Exception as e:
    print('FAIL ohne Auth-Header:', e)
url2 = 'http://127.0.0.1:8000/shaduler/api/webhook/email-index/'
req2 = urllib.request.Request(url2, data=body, method='POST', headers={
    'Authorization': f'Token {tok}', 'Content-Type': 'application/json',
})
try:
    with urllib.request.urlopen(req2, timeout=20) as r:
        print(f'Ref mit Auth-Header: HTTP {r.status}')
except Exception as e:
    print('FAIL mit Auth:', e)
PY
echo

echo "=== 9) Fix-Kommandos ==="
echo "  bash scripts/SYNC-abpe-shaduler-files.sh"
echo "  cd /opt/abpe/backend && /opt/abpe/venv311/bin/python manage.py register_scheduler_jobs"
echo "  supervisorctl restart abpe-django abpe-celery"
echo "  Hard-Reload Browser"
echo "======== ENDE PROBE ========"
