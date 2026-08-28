#!/usr/bin/env bash
# Deploy „Neu“-Knopf auf dem Aufgaben-Tab nach ucs5.
# Live bleibt unangetastet, bis du dieses Skript selbst startest.
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/aufgaben-neu-button-ee01
#   bash <(git show origin/cursor/aufgaben-neu-button-ee01:scripts/SAFE-shaduler-aufgabe-neu-deploy.sh)
#   Browser: Ctrl+F5 auf /shaduler/?tab=aufgaben
#
# Liest die Dateien per git show von origin (kein divergenter Working-Tree).
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/aufgaben-neu-button-ee01}"
LIVE_SH="${LIVE_SH:-/opt/abpe/backend/apps/abpe_shaduler}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
STATICFILES="${STATICFILES:-/opt/abpe/backend/staticfiles}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/abpe/backups}"
TS=$(date +%Y%m%d-%H%M%S)
BAK="$BACKUP_ROOT/shaduler-aufgabe-neu-deploy-$TS"

[[ -d "$REPO/.git" ]] || { echo "FAIL: $REPO ist kein git-Repo"; exit 1; }
[[ -d "$LIVE_SH" ]] || { echo "FAIL: $LIVE_SH fehlt"; exit 1; }
[[ -d "$LIVE_UI" ]] || { echo "FAIL: $LIVE_UI fehlt"; exit 1; }

echo "=== git fetch origin $BRANCH ==="
git -C "$REPO" fetch origin "$BRANCH"

REF="origin/$BRANCH"
git_show() {
  local rel="$1"
  git -C "$REPO" show "$REF:$rel"
}

git_show "Repo_abpe/abpe_shaduler/incoming/views.py" >/dev/null
git_show "Repo_abpe/abpe_ui/incoming/mod-shaduler.js" >/dev/null
git_show "Repo_abpe/abpe_ui/incoming/mod-shaduler.css" >/dev/null

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git_show "Repo_abpe/abpe_shaduler/incoming/views.py" > "$TMP/views.py"
git_show "Repo_abpe/abpe_ui/incoming/mod-shaduler.js" > "$TMP/mod-shaduler.js"
git_show "Repo_abpe/abpe_ui/incoming/mod-shaduler.css" > "$TMP/mod-shaduler.css"

grep -q "def _parse_faellig" "$TMP/views.py" \
  || { echo "FAIL: views.py ohne _parse_faellig"; exit 1; }
grep -q "faellig_am=faellig_am" "$TMP/views.py" \
  || { echo "FAIL: api_aufgabe_create ohne faellig_am"; exit 1; }
grep -q "id=\"sh-aufgabe-neu\"" "$TMP/mod-shaduler.js" \
  || { echo "FAIL: mod-shaduler.js ohne sh-aufgabe-neu"; exit 1; }
grep -q "function openManualAufgabeCreate" "$TMP/mod-shaduler.js" \
  || { echo "FAIL: mod-shaduler.js ohne openManualAufgabeCreate"; exit 1; }
grep -q "function bindAufgabeNeu" "$TMP/mod-shaduler.js" \
  || { echo "FAIL: mod-shaduler.js ohne bindAufgabeNeu"; exit 1; }
grep -q "sh-aufgabe-neu\|sh-due-grid-2" "$TMP/mod-shaduler.css" \
  || { echo "FAIL: mod-shaduler.css ohne Neu-Button-Styles"; exit 1; }

python3 -c "import ast; ast.parse(open('$TMP/views.py',encoding='utf-8').read())"

mkdir -p "$BAK"/{sh,ui}
echo "Backup → $BAK"

deploy_one() {
  local src="$1" dst="$2" bakdir="$3"
  mkdir -p "$(dirname "$dst")" "$bakdir"
  if [[ -f "$dst" ]]; then
    cp -a "$dst" "$bakdir/$(basename "$dst")"
  fi
  cp -a "$src" "$dst"
  echo "OK $(basename "$src") → $dst"
}

deploy_one "$TMP/views.py" "$LIVE_SH/views.py" "$BAK/sh"

mkdir -p "$LIVE_UI/static/abpe_ui/js/mod" "$LIVE_UI/static/abpe_ui/css/mod"
deploy_one "$TMP/mod-shaduler.js" "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js" "$BAK/ui"
deploy_one "$TMP/mod-shaduler.css" "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css" "$BAK/ui"
if [[ -d "$STATICFILES/abpe_ui/js/mod" ]]; then
  deploy_one "$TMP/mod-shaduler.js" "$STATICFILES/abpe_ui/js/mod/mod-shaduler.js" "$BAK/ui"
fi
if [[ -d "$STATICFILES/abpe_ui/css/mod" ]]; then
  deploy_one "$TMP/mod-shaduler.css" "$STATICFILES/abpe_ui/css/mod/mod-shaduler.css" "$BAK/ui"
fi

find "$LIVE_SH" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

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
echo "  Browser Ctrl+F5 → /shaduler/?tab=aufgaben → Knopf „Neu“"
echo "  Dialog: Titel, Art, Fälligkeit, Notiz → Aufgabe anlegen"
if [[ "$RESTARTED" -eq 0 ]]; then
  echo "  Noch nötig: supervisorctl restart abpe-django"
fi
echo "Restore: Dateien aus $BAK/sh bzw. $BAK/ui zurückkopieren"
