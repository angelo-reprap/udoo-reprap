#!/bin/bash
# Portal Dropdown-Fix auf ucs5 deployen (aus Repo incoming/)
#
#   cd /mnt/public/udoo-reprap && git fetch origin cursor/email-studio-undo-i18n-bf44
#   bash Repo_abpe/abpe_ui/incoming/RUN-deploy-lang-dropdown-ucs5.sh

set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${ABPE_BACKEND:-/opt/abpe/backend}"
BR="${BR:-origin/cursor/email-studio-undo-i18n-bf44}"
UI="Repo_abpe/abpe_ui/incoming"
CRM="Repo_abpe/abpe_crm/incoming"

cd "$REPO"
git fetch origin cursor/email-studio-undo-i18n-bf44 2>/dev/null || true

deploy() {
  local src="$1" dest="$2"
  git show "$BR:$src" > "$dest"
  echo "OK: $dest"
}

echo "=== Portal Dropdown-Fix ==="
deploy "$UI/header.html" \
  "$BACKEND/apps/abpe_ui/templates/abpe_ui/components/header.html"
deploy "$UI/core-language.js" \
  "$BACKEND/apps/abpe_ui/static/abpe_ui/js/core/core-language.js"

echo ""
echo "=== CRM: Doppelload-Schutz (Compose) ==="
deploy "$CRM/core-language.js" \
  "$BACKEND/apps/abpe_crm/static/abpe_crm/js/core-language.js"

echo ""
echo "=== collectstatic ==="
cd "$BACKEND"
source venv/bin/activate 2>/dev/null || source venv311/bin/activate 2>/dev/null || true
python manage.py collectstatic --noinput 2>/dev/null || true

echo ""
echo "Fertig. Hard-Reload im Browser (Ctrl+Shift+R)."
