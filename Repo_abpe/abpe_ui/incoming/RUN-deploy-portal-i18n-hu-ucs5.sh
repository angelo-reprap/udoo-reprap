#!/bin/bash
# Portal Phase 1: HU set-language + meta.json + i18n_translator
# Backup → Deploy (ucs5)
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/portal-i18n-phase1-bf44
#   git show origin/cursor/portal-i18n-phase1-bf44:Repo_abpe/abpe_ui/incoming/RUN-deploy-portal-i18n-hu-ucs5.sh | bash

set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${ABPE_BACKEND:-/opt/abpe/backend}"
BR="${BR:-origin/cursor/portal-i18n-phase1-bf44}"
UI="Repo_abpe/abpe_ui/incoming"
NOTE="${NOTE:-vor portal-i18n-hu-phase1}"
BR_PY="$BACKEND/Archiv/backup_restore.py"

cd "$REPO"
git fetch origin cursor/portal-i18n-phase1-bf44 2>/dev/null || true

if [[ ! -f "$BR_PY" ]]; then
  echo "FEHLER: $BR_PY nicht gefunden." >&2
  exit 1
fi

backup() {
  local rel="$1"
  if [[ -f "$BACKEND/$rel" ]]; then
    python3 "$BR_PY" -save "$rel" -m "$NOTE"
    echo "BACKUP: $rel"
  else
    echo "SKIP backup (fehlt): $rel"
  fi
}

deploy() {
  local src="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  git show "$BR:$src" > "$dest"
  echo "OK: $dest"
}

echo "=== 1. BACKUP ==="
backup apps/abpe_ui/api/components/set_language.py
backup apps/abpe_ui/static/abpe_ui/i18n/hu/meta.json
backup apps/abpe_ui/bin/i18n_translator.py

echo ""
echo "=== 2. DEPLOY ==="
deploy "$UI/api_components/set_language.py" \
  "$BACKEND/apps/abpe_ui/api/components/set_language.py"
deploy "$UI/i18n/hu/meta.json" \
  "$BACKEND/apps/abpe_ui/static/abpe_ui/i18n/hu/meta.json"
deploy "$UI/i18n_translator.py" \
  "$BACKEND/apps/abpe_ui/bin/i18n_translator.py"

echo ""
echo "=== 3. Optional: meta.json per Translator neu (nur wenn gewünscht) ==="
echo "  cd $BACKEND"
echo "  python3 apps/abpe_ui/bin/i18n_translator.py --lang hu --check"
echo "  # meta neu: python3 apps/abpe_ui/bin/i18n_translator.py --lang hu --force  # übersetzt ALLES!"

echo ""
echo "=== 4. collectstatic ==="
cd "$BACKEND"
if [[ -f venv311/bin/activate ]]; then source venv311/bin/activate
elif [[ -f venv/bin/activate ]]; then source venv/bin/activate
fi
python manage.py collectstatic --noinput 2>/dev/null || true

echo ""
echo "Fertig. HU wählen → POST /api/set-language/ sollte 200 liefern."
echo "Restore: python3 Archiv/backup_restore.py -restore <pfad>"
