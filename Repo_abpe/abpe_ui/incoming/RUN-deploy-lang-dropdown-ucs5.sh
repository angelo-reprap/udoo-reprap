#!/bin/bash
# Portal Dropdown-Fix: Backup → Deploy (ucs5)
#
# Auf JEDEM Branch ausführbar:
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/email-studio-undo-i18n-bf44
#   git show origin/cursor/email-studio-undo-i18n-bf44:Repo_abpe/abpe_ui/incoming/RUN-deploy-lang-dropdown-ucs5.sh | bash

set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${ABPE_BACKEND:-/opt/abpe/backend}"
BR="${BR:-origin/cursor/email-studio-undo-i18n-bf44}"
UI="Repo_abpe/abpe_ui/incoming"
CRM="Repo_abpe/abpe_crm/incoming"
NOTE="${NOTE:-vor lang-dropdown-fix}"
BR_PY="$BACKEND/Archiv/backup_restore.py"

cd "$REPO"
git fetch origin cursor/email-studio-undo-i18n-bf44 2>/dev/null || true

if [[ ! -f "$BR_PY" ]]; then
  echo "FEHLER: $BR_PY nicht gefunden — Backup zuerst einrichten." >&2
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

echo "=== 1. BACKUP Live-Dateien ==="
backup apps/abpe_ui/templates/abpe_ui/components/header.html
backup apps/abpe_ui/static/abpe_ui/js/core/core-language.js
backup apps/abpe_crm/static/abpe_crm/js/core-language.js

echo ""
echo "=== 2. DEPLOY aus Repo ($BR) ==="
deploy "$UI/header.html" \
  "$BACKEND/apps/abpe_ui/templates/abpe_ui/components/header.html"
deploy "$UI/core-language.js" \
  "$BACKEND/apps/abpe_ui/static/abpe_ui/js/core/core-language.js"
deploy "$CRM/core-language.js" \
  "$BACKEND/apps/abpe_crm/static/abpe_crm/js/core-language.js"

echo ""
echo "=== 3. collectstatic ==="
cd "$BACKEND"
if [[ -f venv311/bin/activate ]]; then source venv311/bin/activate
elif [[ -f venv/bin/activate ]]; then source venv/bin/activate
fi
python manage.py collectstatic --noinput 2>/dev/null || true

echo ""
echo "Fertig. Hard-Reload (Ctrl+Shift+R)."
echo "Restore: python3 Archiv/backup_restore.py -restore <pfad>"
