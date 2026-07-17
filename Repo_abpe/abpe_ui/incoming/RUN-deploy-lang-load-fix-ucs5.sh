#!/bin/bash
# Fix: loadLanguage global + Email Studio Modul-i18n nach Sprachwechsel
# Backup → Deploy (ucs5)
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/portal-i18n-phase1-bf44
#   git show origin/cursor/portal-i18n-phase1-bf44:Repo_abpe/abpe_ui/incoming/RUN-deploy-lang-load-fix-ucs5.sh | bash

set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${ABPE_BACKEND:-/opt/abpe/backend}"
BR="${BR:-origin/cursor/portal-i18n-phase1-bf44}"
NOTE="${NOTE:-vor lang-load-fix}"
BR_PY="$BACKEND/Archiv/backup_restore.py"

cd "$REPO"
git fetch origin cursor/portal-i18n-phase1-bf44 2>/dev/null || true

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
backup apps/abpe_ui/templates/abpe_ui/base.html
backup apps/abpe_ui/templates/abpe_ui/modules/email_studio/base.html
backup apps/abpe_crm/templates/abpe_crm/email_compose.html

echo ""
echo "=== 2. DEPLOY ==="
deploy Repo_abpe/abpe_ui/incoming/core-language.js \
  "$BACKEND/apps/abpe_ui/static/abpe_ui/js/core/core-language.js"
deploy Repo_abpe/abpe_ui/incoming/base.html \
  "$BACKEND/apps/abpe_ui/templates/abpe_ui/base.html"
deploy Repo_abpe/email_studio/incoming/base.html \
  "$BACKEND/apps/abpe_ui/templates/abpe_ui/modules/email_studio/base.html"
deploy Repo_abpe/abpe_crm/incoming/email_compose.html \
  "$BACKEND/apps/abpe_crm/templates/abpe_crm/email_compose.html"

echo ""
echo "=== 3. collectstatic + restart ==="
cd "$BACKEND"
if [[ -f venv311/bin/activate ]]; then source venv311/bin/activate
elif [[ -f venv/bin/activate ]]; then source venv/bin/activate
fi
python manage.py collectstatic --noinput
supervisorctl restart abpe-django

echo ""
echo "Fertig. Hard-Reload Email Studio → Sprache wechseln → es.* Labels sollten mitwechseln."
