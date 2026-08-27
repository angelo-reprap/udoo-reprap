# Deploy Aufgaben-Delegation (Wiedervorlagen an Kollegen) nach ucs5.
# Live bleibt unangetastet, bis du dieses Skript selbst startest.
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin && git pull origin cursor/aufgaben-delegation-ee01
#   bash scripts/SAFE-shaduler-delegation-deploy.sh
#   Browser: Ctrl+F5 auf /shaduler/?tab=aufgaben
#
# Enthält: Migration 0007 (M2M delegiert_an), API /shaduler/api/team/,
# Popup „Delegiert an“ (eine oder mehrere Personen), Listen-Badge.
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
LIVE_SH="${LIVE_SH:-/opt/abpe/backend/apps/abpe_shaduler}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
STATICFILES="${STATICFILES:-/opt/abpe/backend/staticfiles}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/abpe/backups}"
TS=$(date +%Y%m%d-%H%M%S)
BAK="$BACKUP_ROOT/shaduler-delegation-deploy-$TS"

SRC_SH="$REPO/Repo_abpe/abpe_shaduler/incoming"
SRC_UI="$REPO/Repo_abpe/abpe_ui/incoming"

PY="${PY:-/opt/abpe/venv311/bin/python}"
if [[ ! -x "$PY" ]]; then
  if [[ -x "$BACKEND/venv/bin/python" ]]; then
    PY="$BACKEND/venv/bin/python"
  else
    PY=python3
  fi
fi

must_sh=(
  models.py
  views.py
  urls.py
  admin.py
  services/aufgaben_service.py
  migrations/0007_aufgabe_delegiert_an.py
)
for f in "${must_sh[@]}"; do
  [[ -f "$SRC_SH/$f" ]] || { echo "FAIL fehlt: $SRC_SH/$f"; exit 1; }
done

SRC_JS="$SRC_UI/mod-shaduler.js"
if [[ ! -f "$SRC_JS" ]]; then
  SRC_JS="$SRC_UI/static_abpe_ui/js/mod/mod-shaduler.js"
fi
SRC_CSS="$SRC_UI/mod-shaduler.css"
if [[ ! -f "$SRC_CSS" ]]; then
  SRC_CSS="$SRC_UI/static_abpe_ui/css/mod/mod-shaduler.css"
fi
[[ -f "$SRC_JS" ]] || { echo "FAIL fehlt: mod-shaduler.js"; exit 1; }
[[ -f "$SRC_CSS" ]] || { echo "FAIL fehlt: mod-shaduler.css"; exit 1; }

grep -q "delegiert_an" "$SRC_SH/models.py" \
  || { echo "FAIL: models.py ohne delegiert_an"; exit 1; }
grep -q "def set_delegates" "$SRC_SH/services/aufgaben_service.py" \
  || { echo "FAIL: aufgaben_service ohne set_delegates"; exit 1; }
grep -q "def api_team" "$SRC_SH/views.py" \
  || { echo "FAIL: views.py ohne api_team"; exit 1; }
grep -q "api/team/" "$SRC_SH/urls.py" \
  || { echo "FAIL: urls.py ohne api/team/"; exit 1; }
grep -q "renderDelegatePicker" "$SRC_JS" \
  || { echo "FAIL: mod-shaduler.js ohne renderDelegatePicker"; exit 1; }
grep -q "lastNameLetter" "$SRC_JS" \
  || { echo "FAIL: mod-shaduler.js ohne Nachnamen-Gruppierung"; exit 1; }
grep -q "Benutzerverwaltung" "$SRC_SH/services/aufgaben_service.py" \
  || { echo "FAIL: team_users nicht an Benutzerverwaltung gekoppelt"; exit 1; }
grep -q "sh-m-delegate" "$SRC_JS" \
  || { echo "FAIL: mod-shaduler.js ohne sh-m-delegate"; exit 1; }
grep -q "sh-delegate" "$SRC_CSS" \
  || { echo "FAIL: mod-shaduler.css ohne .sh-delegate"; exit 1; }

python3 -c "import ast; ast.parse(open('$SRC_SH/models.py',encoding='utf-8').read())"
python3 -c "import ast; ast.parse(open('$SRC_SH/views.py',encoding='utf-8').read())"
python3 -c "import ast; ast.parse(open('$SRC_SH/urls.py',encoding='utf-8').read())"
python3 -c "import ast; ast.parse(open('$SRC_SH/services/aufgaben_service.py',encoding='utf-8').read())"
python3 -c "import ast; ast.parse(open('$SRC_SH/migrations/0007_aufgabe_delegiert_an.py',encoding='utf-8').read())"

mkdir -p "$BAK"/{sh,ui}
echo "Backup → $BAK"

deploy_one() {
  local src="$1" dst="$2" bakdir="$3"
  mkdir -p "$(dirname "$dst")" "$bakdir"
  if [[ -f "$dst" ]]; then
    mkdir -p "$bakdir/$(dirname "${dst##*/}")"
    cp -a "$dst" "$bakdir/$(basename "$dst")"
  fi
  cp -a "$src" "$dst"
  echo "OK $(basename "$src") → $dst"
}

deploy_one "$SRC_SH/models.py" "$LIVE_SH/models.py" "$BAK/sh"
deploy_one "$SRC_SH/views.py" "$LIVE_SH/views.py" "$BAK/sh"
deploy_one "$SRC_SH/urls.py" "$LIVE_SH/urls.py" "$BAK/sh"
deploy_one "$SRC_SH/admin.py" "$LIVE_SH/admin.py" "$BAK/sh"
deploy_one "$SRC_SH/services/aufgaben_service.py" "$LIVE_SH/services/aufgaben_service.py" "$BAK/sh"
mkdir -p "$LIVE_SH/migrations"
deploy_one "$SRC_SH/migrations/0007_aufgabe_delegiert_an.py" \
  "$LIVE_SH/migrations/0007_aufgabe_delegiert_an.py" "$BAK/sh"

mkdir -p "$LIVE_UI/static/abpe_ui/js/mod" "$LIVE_UI/static/abpe_ui/css/mod"
deploy_one "$SRC_JS" "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js" "$BAK/ui"
deploy_one "$SRC_CSS" "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css" "$BAK/ui"
if [[ -d "$STATICFILES/abpe_ui/js/mod" ]]; then
  deploy_one "$SRC_JS" "$STATICFILES/abpe_ui/js/mod/mod-shaduler.js" "$BAK/ui"
fi
if [[ -d "$STATICFILES/abpe_ui/css/mod" ]]; then
  deploy_one "$SRC_CSS" "$STATICFILES/abpe_ui/css/mod/mod-shaduler.css" "$BAK/ui"
fi

find "$LIVE_SH" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

echo "=== migrate abpe_shaduler ==="
if [[ -f "$BACKEND/manage.py" ]]; then
  ( cd "$BACKEND" && "$PY" manage.py migrate abpe_shaduler --noinput )
else
  echo "WARN: $BACKEND/manage.py fehlt — migrate manuell:"
  echo "  cd $BACKEND && $PY manage.py migrate abpe_shaduler --noinput"
fi

RESTARTED=0
if command -v supervisorctl >/dev/null 2>&1; then
  if supervisorctl restart abpe-django; then
    RESTARTED=1
    echo "OK supervisorctl restart abpe-django"
  else
    echo "WARN: supervisorctl restart fehlgeschlagen — bitte manuell"
  fi
else
  echo "WARN: supervisorctl nicht gefunden — Django manuell neu starten"
fi

echo
echo "Deploy fertig. Backup: $BAK"
echo "  Browser Ctrl+F5 → /shaduler/?tab=aufgaben → Wiedervorlage öffnen"
echo "  Unter „Geprüft — entscheiden“: Delegiert an (Verena, Annett, …)"
if [[ "$RESTARTED" -eq 0 ]]; then
  echo "  Noch nötig: supervisorctl restart abpe-django"
fi
echo "Restore: Dateien aus $BAK/sh bzw. $BAK/ui zurückkopieren"
