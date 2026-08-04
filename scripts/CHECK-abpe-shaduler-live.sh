#!/usr/bin/env bash
# Live vs Repo-Check für abpe_shaduler (auf ucs5 ausführen)
set -euo pipefail
REPO="${REPO:-/mnt/public/udoo-reprap}"
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

echo
echo "Fertig. Bei MISS → SYNC-abpe-shaduler-files.sh ausführen."
echo "Bei URL FAIL → nano urls.py und shaduler/ VOR abpe_ui Catch-all."
