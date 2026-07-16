#!/bin/bash
# Email Studio Phase 2b — Modul/Signatur CRUD im Studio
set -euo pipefail

BACKEND=/opt/abpe/backend
REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/email-studio-phase2b-crud-bf44}"
BR="origin/${BRANCH}"
R="Repo_abpe/email_studio/incoming"
VENV="${VENV:-$BACKEND/venv311/bin/activate}"

echo "=== Email Studio Phase 2b Deploy ==="
cd "$REPO"
git fetch origin "$BRANCH"

git show "$BR:$R/studio.html" > "$BACKEND/apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html"
git show "$BR:$R/es-studio.js" > "$BACKEND/apps/abpe_email_studio/static/email_studio/js/es-studio.js"
git show "$BR:$R/mod-email_studio.css" > "$BACKEND/apps/abpe_ui/static/abpe_ui/css/mod/mod-email_studio.css"
git show "$BR:$R/email_studio.json" > "$BACKEND/apps/abpe_ui/static/abpe_ui/i18n/de/modules/email_studio/email_studio.json"

cd "$BACKEND"
source "$VENV"
python manage.py collectstatic --noinput

grep -c "_resetNewSignature" "$BACKEND/staticfiles/email_studio/js/es-studio.js"
supervisorctl restart abpe-django
echo "✓ Fertig — Strg+Shift+R"
