#!/usr/bin/env bash
# Deploy EDMS-Favoriten + PDF-Viewer nach ucs5. Live-Backup, dann gezielte Dateien.
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin && git pull origin cursor/matching-templates-dms-ee01
#   bash scripts/SAFE-edms-favoriten-deploy.sh
#   Browser: Ctrl+F5 auf /crm/dms/
#
# Python-Teil braucht Django-Reload:
#   supervisorctl restart abpe-django
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
LIVE_CRM="${LIVE_CRM:-/opt/abpe/backend/apps/abpe_crm}"
STATICFILES="${STATICFILES:-/opt/abpe/backend/staticfiles}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/abpe/backups}"
TS=$(date +%Y%m%d-%H%M%S)
BAK="$BACKUP_ROOT/edms-favoriten-deploy-$TS"
SRC="$REPO/Repo_abpe/abpe_crm/incoming"

must=(
  templates/abpe_crm/tabs/edms_tab.html
  static/abpe_crm/js/mod-edms.js
  static/abpe_crm/css/mod-edms.css
  static/abpe_crm/i18n/de/modules/crm_edms/crm_dms.json
  static/abpe_crm/i18n/en/modules/crm_edms/crm_dms.json
  views_edms_file.py
)
for f in "${must[@]}"; do
  [[ -f "$SRC/$f" ]] || { echo "FAIL fehlt: $SRC/$f"; exit 1; }
done
grep -q "setFavTab" "$SRC/static/abpe_crm/js/mod-edms.js" \
  || { echo "FAIL: mod-edms.js ohne Favoriten"; exit 1; }
grep -q "edms-btn-favoriten" "$SRC/templates/abpe_crm/tabs/edms_tab.html" \
  || { echo "FAIL: edms_tab.html ohne Favoriten-Schalter"; exit 1; }
grep -q "edmsFile" "$SRC/static/abpe_crm/js/mod-edms.js" \
  || { echo "FAIL: mod-edms.js ohne Blob-Viewer (edmsFile)"; exit 1; }
grep -q "_api_edms_file" "$SRC/views_edms_file.py" \
  || { echo "FAIL: views_edms_file.py ohne _api_edms_file"; exit 1; }
grep -q "_parse_win_or_rel" "$SRC/views_edms_file.py" \
  || { echo "FAIL: views_edms_file.py ohne O:/X:-Mapping"; exit 1; }
python3 -c "import ast; ast.parse(open('$SRC/views_edms_file.py',encoding='utf-8').read())"

mkdir -p "$BAK"
echo "Backup → $BAK"

deploy_one() {
  local rel="$1"
  local src="$SRC/$rel"
  local dst="$LIVE_CRM/$rel"
  mkdir -p "$(dirname "$dst")" "$BAK/$(dirname "$rel")"
  if [[ -f "$dst" ]]; then
    cp -a "$dst" "$BAK/$rel"
  fi
  cp -a "$src" "$dst"
  echo "OK $rel → $dst"
  local sf="$STATICFILES/${rel#static/}"
  if [[ "$rel" == static/* && -d "$STATICFILES" ]]; then
    mkdir -p "$(dirname "$sf")"
    cp -a "$src" "$sf"
    echo "OK staticfiles $(basename "$sf")"
  fi
}

for f in "${must[@]}"; do
  deploy_one "$f"
done

for extra in urls.py views.py; do
  if [[ -f "$LIVE_CRM/$extra" ]]; then
    mkdir -p "$BAK"
    cp -a "$LIVE_CRM/$extra" "$BAK/$extra"
  fi
done

echo "=== urls.py Route ==="
python3 - << PY
from pathlib import Path
p = Path("$LIVE_CRM/urls.py")
s = p.read_text(encoding="utf-8")
if "api_edms_file" in s:
    print("  Route existiert schon")
else:
    anchor = "    path('api/recording/<int:rec_id>/delete/',  views.api_recording_delete, name='api_recording_delete'),"
    line = anchor + "\\n    path('api/edms/file/<uuid:uuid>/',          views.api_edms_file,       name='api_edms_file'),"
    if s.count(anchor) != 1:
        raise SystemExit(f"FAIL urls.py Anker {s.count(anchor)}x")
    p.write_text(s.replace(anchor, line), encoding="utf-8")
    print("  Route eingetragen")
PY

echo "=== views.py Wrapper ==="
python3 - << PY
from pathlib import Path
import ast
p = Path("$LIVE_CRM/views.py")
s = p.read_text(encoding="utf-8")
if "api_edms_file" in s and "views_edms_file" in s:
    print("  Wrapper existiert schon")
else:
    add = """
from .views_edms_file import _api_edms_file as _edms_file_impl
api_edms_file = login_or_token_required(_edms_file_impl)
"""
    p.write_text(s.rstrip() + "\\n" + add + "\\n", encoding="utf-8")
    print("  Wrapper angehängt")
ast.parse(p.read_text(encoding="utf-8"))
print("  views.py Syntax OK")
PY

echo "=== Syntax Live-Modul ==="
python3 -c "import ast; ast.parse(open('$LIVE_CRM/views_edms_file.py',encoding='utf-8').read()); ast.parse(open('$LIVE_CRM/urls.py',encoding='utf-8').read())"

RESTARTED=0
if command -v supervisorctl >/dev/null 2>&1; then
  if supervisorctl restart abpe-django; then
    RESTARTED=1
    echo "OK supervisorctl restart abpe-django"
  else
    echo "HINWEIS: supervisorctl restart abpe-django fehlgeschlagen — bitte selbst neu laden"
  fi
else
  echo "HINWEIS: supervisorctl nicht gefunden — Django neu laden:"
  echo "  supervisorctl restart abpe-django"
fi

echo
echo "Deploy fertig. Backup: $BAK"
echo "  Browser Ctrl+F5 → /crm/dms/ → PDF (Rechnung und AID-CV)"
if [[ "$RESTARTED" -ne 1 ]]; then
  echo "  Python-Endpoint erst nach: supervisorctl restart abpe-django"
fi
echo "Restore JS: cp -a $BAK/static/abpe_crm/js/mod-edms.js $LIVE_CRM/static/abpe_crm/js/mod-edms.js"
echo "Restore streamer: cp -a $BAK/views_edms_file.py $LIVE_CRM/views_edms_file.py"
