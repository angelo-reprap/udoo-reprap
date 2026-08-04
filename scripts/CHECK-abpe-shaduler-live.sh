#!/usr/bin/env bash
# Live vs Repo-Check für abpe_shaduler (auf ucs5 ausführen)
set -euo pipefail
REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"
LIVE_APP="${LIVE_APP:-/opt/abpe/backend/apps/abpe_shaduler}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
URLS="${URLS:-/opt/abpe/backend/abpe_backend/urls.py}"
APPS="${APPS:-/opt/abpe/backend/abpe_backend/settings/apps.py}"

echo "=== 1) Register ==="
grep -n "abpe_shaduler" "$APPS" || echo "FEHLT in apps.py"
grep -n "shaduler" "$URLS" || echo "FEHLT in urls.py"

echo
echo "=== 2) URL-Reihenfolge (shaduler MUSS vor path('', abpe_ui) stehen) ==="
python3 - <<'PY' "$URLS"
import re, sys
text = open(sys.argv[1], encoding='utf-8').read()
# crude: find positions
m_ui = re.search(r"path\(\s*''\s*,\s*include\(\s*['\"]apps\.abpe_ui\.urls", text)
m_sh = re.search(r"path\(\s*['\"]shaduler/", text)
if not m_sh:
    print("FAIL: kein shaduler/-Eintrag")
elif not m_ui:
    print("WARN: abpe_ui Catch-all nicht gefunden")
elif m_sh.start() < m_ui.start():
    print("OK: shaduler/ steht VOR abpe_ui Catch-all")
else:
    print("FAIL: shaduler/ steht NACH path('', abpe_ui) — wird nie gematcht!")
    print("      → Eintrag VOR die Zeile mit path('', include('apps.abpe_ui.urls')) verschieben")
PY

echo
echo "=== 3) Live-App vorhanden? ==="
if [[ -d "$LIVE_APP" ]]; then
  echo "OK dir $LIVE_APP"
  for f in apps.py models.py views.py urls.py templates/shaduler/index.html scheduler_client.py; do
    [[ -f "$LIVE_APP/$f" ]] && echo "  OK  $f" || echo "  MISS $f"
  done
else
  echo "FEHLT: $LIVE_APP — noch nicht gerysnct"
fi

echo
echo "=== 4) UI-Modul / Static / i18n ==="
[[ -f "$LIVE_UI/templates/abpe_ui/modules/shaduler/module.json" ]] \
  && echo "OK module.json" || echo "MISS module.json"
[[ -f "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css" ]] \
  && echo "OK mod-shaduler.css" || echo "MISS mod-shaduler.css"
[[ -f "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js" ]] \
  && echo "OK mod-shaduler.js" || echo "MISS mod-shaduler.js"
[[ -f "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler-kalender.js" ]] \
  && echo "OK mod-shaduler-kalender.js" || echo "MISS kalender.js"
for lang in de en; do
  [[ -f "$LIVE_UI/static/abpe_ui/i18n/$lang/modules/shaduler/shaduler.json" ]] \
    && echo "OK i18n $lang" || echo "MISS i18n $lang"
done

echo
echo "=== 5) Portal-Core (bereits Live — NICHT Teil des Shaduler-Patches) ==="
for f in \
  static/abpe_ui/css/core-theme.css \
  static/abpe_ui/js/core-theme.js \
  static/abpe_ui/js/core-language.js
 do
  [[ -f "$LIVE_UI/$f" ]] && echo "OK  $f" || echo "MISS $f (Portal-Basis prüfen)"
done
# themes.py falls vorhanden
find "$LIVE_UI" -name 'themes.py' 2>/dev/null | head -5 || true

echo
echo "=== 6) Repo-Branch erreichbar? ==="
cd "$REPO"
git fetch origin cursor/abpe-shaduler-scaffold-7f07 2>/dev/null || true
git rev-parse --short origin/cursor/abpe-shaduler-scaffold-7f07 2>/dev/null \
  && echo "OK remote branch" || echo "MISS remote branch"

BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"

echo
echo "=== 7) tasks.py Syntax (kein 'function '-Typo) ==="
if [[ -f "$LIVE_APP/tasks.py" ]]; then
  if grep -nE '^[[:space:]]*function[[:space:]]+shaduler_' "$LIVE_APP/tasks.py"; then
    echo "FAIL: tasks.py enthält noch 'function shaduler_…' — SYNC + restart"
  else
    echo "OK: keine function-Typos in tasks.py"
  fi
  (cd "$BACKEND" && "$PYBIN" -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from apps.abpe_shaduler import tasks
print('OK import JOB_HANDLERS:', sorted(set(tasks.JOB_HANDLERS)))
") 2>/dev/null || echo "WARN: tasks-Import fehlgeschlagen (Django/Settings prüfen)"
else
  echo "MISS tasks.py"
fi

echo
echo "=== 8) Webhook-Auth Smoke (inbox-poll) ==="
set +e
(
  cd "$BACKEND" || exit 1
  "$PYBIN" - <<'PY'
import os, django, urllib.request, urllib.error
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from django.conf import settings
tok = getattr(settings, 'SCHEDULER_SERVICE_TOKEN', '') or ''
if not tok:
    print('FAIL: SCHEDULER_SERVICE_TOKEN leer in Django-Settings')
    raise SystemExit(0)
req = urllib.request.Request(
    'http://127.0.0.1:8000/shaduler/api/webhook/inbox-poll/',
    data=b'{"job":"inbox_poll"}',
    headers={'Authorization': f'Token {tok}', 'Content-Type': 'application/json'},
    method='POST',
)
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()[:300]
        print(f'OK HTTP {r.status}: {body!r}')
except urllib.error.HTTPError as e:
    body = e.read()[:200]
    print(f'FAIL HTTP {e.code}: {body!r}')
    if e.code == 401:
        print('  → Token-Mismatch: Scheduler-PUSH vs Django SCHEDULER_SERVICE_TOKEN')
except Exception as e:
    print(f'FAIL: {e}')
PY
) || echo "WARN: Webhook-Smoke übersprungen"
set -e

echo
echo "Fertig. Bei MISS → SYNC-abpe-shaduler-files.sh ausführen."
echo "Bei URL FAIL → nano urls.py und shaduler/ VOR abpe_ui Catch-all."
