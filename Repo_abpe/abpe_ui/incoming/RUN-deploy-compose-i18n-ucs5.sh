#!/bin/bash
# Compose i18n-Fix: Backup → Deploy (ucs5)
# Behebt: doppeltes CRM core-language.js löscht es.*-Übersetzungen
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/portal-i18n-phase1-bf44
#   git show origin/cursor/portal-i18n-phase1-bf44:Repo_abpe/abpe_ui/incoming/RUN-deploy-compose-i18n-ucs5.sh | bash

set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${ABPE_BACKEND:-/opt/abpe/backend}"
BR="${BR:-origin/cursor/portal-i18n-phase1-bf44}"
NOTE="${NOTE:-vor compose-i18n-fix}"
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
  fi
}

deploy() {
  local src="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  git show "$BR:$src" > "$dest"
  echo "OK: $dest"
}

echo "=== 1. BACKUP ==="
backup apps/abpe_ui/static/abpe_ui/js/core/core-language.js
backup apps/abpe_crm/templates/abpe_crm/email_compose.html

echo ""
echo "=== 2. DEPLOY ==="
deploy "Repo_abpe/abpe_ui/incoming/core-language.js" \
  "$BACKEND/apps/abpe_ui/static/abpe_ui/js/core/core-language.js"
deploy "Repo_abpe/abpe_crm/incoming/email_compose.html" \
  "$BACKEND/apps/abpe_crm/templates/abpe_crm/email_compose.html"

echo ""
echo "=== 3. collectstatic ==="
cd "$BACKEND"
if [[ -f venv311/bin/activate ]]; then source venv311/bin/activate
elif [[ -f venv/bin/activate ]]; then source venv/bin/activate
fi
python manage.py collectstatic --noinput 2>/dev/null || true

echo ""
echo "Fertig. Hard-Reload auf /crm/email/compose/"
echo ""
echo "Optional HU für CRM (fehlt noch auf Live):"
echo "  mkdir -p apps/abpe_crm/static/abpe_crm/i18n/hu"
echo "  python3 apps/abpe_crm/bin/i18n_translator.py --lang hu"
