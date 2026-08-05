#!/usr/bin/env bash
# Live-Diagnose: Posteingang Soft-Poll + ES-Indexer (ucs5, copy&paste)
# Usage:
#   bash /mnt/public/udoo-reprap/scripts/PROBE-shaduler-inbox-refresh.sh
# oder nach git fetch:
#   bash <(git -C /mnt/public/udoo-reprap show origin/cursor/abpe-shaduler-scaffold-7f07:scripts/PROBE-shaduler-inbox-refresh.sh)
set -u
BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
STATICFILES="${STATICFILES:-/opt/abpe/backend/staticfiles}"
REPO="${REPO:-/mnt/public/udoo-reprap}"

echo "======== PROBE shaduler inbox refresh $(date -Iseconds) ========"
echo

echo "=== 1) Soft-Poll im App-Static? ==="
APP_JS="$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js"
if [[ -f "$APP_JS" ]]; then
  echo "OK file $APP_JS"
  echo "  mtime=$(stat -c %y "$APP_JS" 2>/dev/null || stat -f %Sm "$APP_JS")"
  rg -n "INBOX_POLL_MS|startInboxPoll|inboxIsBusy|loadInbox\(opts" "$APP_JS" || echo "FAIL: Soft-Poll-Strings fehlen in App-JS"
else
  echo "FAIL: $APP_JS fehlt"
fi
echo

echo "=== 2) Soft-Poll in STATIC_ROOT (was der Browser oft lädt)? ==="
SF_JS="$STATICFILES/abpe_ui/js/mod/mod-shaduler.js"
if [[ -f "$SF_JS" ]]; then
  echo "OK file $SF_JS"
  echo "  mtime=$(stat -c %y "$SF_JS" 2>/dev/null || true)"
  if rg -q "INBOX_POLL_MS|startInboxPoll" "$SF_JS"; then
    echo "OK Soft-Poll in staticfiles"
  else
    echo "FAIL: Soft-Poll FEHLT in staticfiles → collectstatic nötig!"
  fi
else
  echo "WARN: $SF_JS fehlt (Manifest-Hash?)"
  ls -lt "$STATICFILES"/abpe_ui/js/mod/mod-shaduler*.js 2>/dev/null | head -5 || true
  HASHED=$(ls -1 "$STATICFILES"/abpe_ui/js/mod/mod-shaduler*.js 2>/dev/null | head -1 || true)
  if [[ -n "${HASHED:-}" ]]; then
    echo "  prüfe $HASHED"
    rg -n "INBOX_POLL_MS|startInboxPoll" "$HASHED" || echo "FAIL: Soft-Poll fehlt in hashed staticfiles"
  fi
fi
echo

echo "=== 3) Diff App-Static vs Staticfiles (erste 5 Zeilen diff) ==="
if [[ -f "$APP_JS" && -f "$SF_JS" ]]; then
  if cmp -s "$APP_JS" "$SF_JS"; then
    echo "OK identisch"
  else
    echo "FAIL: unterschiedlich — Browser sieht alten Stand ohne collectstatic"
    diff -u "$SF_JS" "$APP_JS" | head -20 || true
  fi
fi
echo

echo "=== 4) Supervisor ==="
supervisorctl status abpe-django abpe-celery abpe-scheduler-loop 2>/dev/null || supervisorctl status all | rg 'abpe-(django|celery|scheduler)' || true
echo

echo "=== 5) Celery: email_index Task registriert? ==="
cd "$BACKEND"
"$PYBIN" - <<'PY'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
try:
    from apps.abpe_shaduler.tasks import email_index_run, shaduler_email_index, JOB_HANDLERS
    print('OK import email_index_run:', getattr(email_index_run, 'name', email_index_run))
    print('OK handlers:', sorted(k for k in JOB_HANDLERS if 'email' in k))
    # delay smoke (nicht ausführen — nur .delay vorhanden?)
    print('OK delay attr:', hasattr(email_index_run, 'delay'))
except Exception as e:
    print('FAIL tasks import:', e)
PY
echo

echo "=== 6) SchedulerJob email_index + letzte Runs ==="
"$PYBIN" - <<'PY'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
try:
    from apps.abpe_scheduler.models import SchedulerJob, SchedulerJobRun
    jobs = SchedulerJob.objects.filter(job_key='email_index').order_by('-id')[:3]
    if not jobs:
        print('FAIL: kein SchedulerJob email_index')
    for j in jobs:
        print(f'JOB id={j.id} status={j.status} rrule={getattr(j, "rrule_string", "")!r} next={j.next_run_at} cb={j.callback_url}')
        print(f'     payload={j.payload}')
        runs = SchedulerJobRun.objects.filter(job=j).order_by('-id')[:5]
        if not runs:
            print('     RUNS: (keine)')
        for r in runs:
            print(f'     RUN id={r.id} status={r.status} sched={r.scheduled_for} http={r.response_status} err={(r.error_message or "")[:120]!r} body={(r.response_body or "")[:160]!r}')
except Exception as e:
    print('FAIL scheduler query:', e)
PY
echo

echo "=== 7) ES newest (angelo + global) ==="
"$PYBIN" manage.py shaduler_inbox_probe --fetch --limit 3 2>/dev/null | rg -n 'newest_date|count=|source=|●|bad_future|reachable' || \
"$PYBIN" - <<'PY'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from apps.abpe_shaduler.services import inbox_service
p = inbox_service.probe(user=None) if hasattr(inbox_service, 'probe') else None
print(p or 'probe() N/A — manage.py shaduler_inbox_probe manuell')
PY
echo

echo "=== 8) Webhook email-index (soll queued:true, <2s) ==="
"$PYBIN" - <<'PY'
import os, django, json, time, urllib.request
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from django.conf import settings
tok = getattr(settings, 'SCHEDULER_SERVICE_TOKEN', '') or ''
if not tok:
    print('FAIL: SCHEDULER_SERVICE_TOKEN leer')
    raise SystemExit(0)
url = 'http://127.0.0.1:8000/shaduler/api/webhook/email-index/'
body = json.dumps({'job': 'email_index', 'since_days': 2, 'folders': 'INBOX', 'incremental': True}).encode()
req = urllib.request.Request(url, data=body, method='POST', headers={
    'Authorization': f'Token {tok}',
    'Content-Type': 'application/json',
})
t0 = time.time()
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read().decode()
        dt = time.time() - t0
        print(f'HTTP {r.status} in {dt:.2f}s')
        print(raw[:500])
        if dt > 5:
            print('WARN: Webhook >5s — sollte Celery-Queue sein (sofort 200)')
        if 'queued' not in raw and 'task_id' not in raw:
            print('WARN: Antwort ohne queued/task_id — alter tasks.py?')
except Exception as e:
    print('FAIL webhook:', e)
PY
echo

echo "=== 9) Kurz-Empfehlung ==="
echo "Wenn (2)/(3) FAIL →:"
echo "  cd $BACKEND && $PYBIN manage.py collectstatic --noinput && supervisorctl restart abpe-django"
echo "Dann Browser: Hard-Reload (Ctrl+Shift+R), Konsole:"
echo "  typeof window.Shaduler;  // und Network: mod-shaduler.js Inhalt nach INBOX_POLL_MS suchen"
echo "Wenn (6) RUNS FAILED timeout → Celery-Fix fehlt / abpe-celery restart"
echo "Wenn Outlook neuer als ES newest →:"
echo "  $PYBIN manage.py index_emails --account angelo --folders INBOX --since-days 1 --incremental"
echo
echo "======== ENDE PROBE — bitte komplette Ausgabe pasten ========"
