#!/bin/bash
# modules.json: Sidebar-Basis-Navigation mit titles (Dashboard, Admin, API Docs)
# Backup → Deploy (ucs5)
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/portal-i18n-phase1-bf44
#   git show origin/cursor/portal-i18n-phase1-bf44:Repo_abpe/abpe_ui/incoming/RUN-deploy-modules-json-ucs5.sh | bash

set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${ABPE_BACKEND:-/opt/abpe/backend}"
BR="${BR:-origin/cursor/portal-i18n-phase1-bf44}"
UI="Repo_abpe/abpe_ui/incoming"
NOTE="${NOTE:-vor modules-json-titles}"
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
backup apps/abpe_ui/modules.json

echo ""
echo "=== 2. DEPLOY ==="
deploy "$UI/modules.json" "$BACKEND/apps/abpe_ui/modules.json"

echo ""
echo "=== 3. Restart Django ==="
cd "$BACKEND"
if [[ -f venv311/bin/activate ]]; then source venv311/bin/activate
elif [[ -f venv/bin/activate ]]; then source venv/bin/activate
fi
supervisorctl restart abpe-django 2>/dev/null || echo "Hinweis: supervisorctl restart abpe-django manuell ausführen"

echo ""
echo "Fertig. Hard-Reload — Sidebar: Dashboard / Admin / API Docs in HU u.a."
echo "Restore: python3 Archiv/backup_restore.py -restore <pfad>"
