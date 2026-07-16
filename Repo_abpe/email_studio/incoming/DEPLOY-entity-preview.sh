#!/bin/bash
# Email Studio — Entity-Vorschau-Fix deployen (ucs5)
# Nutzung:
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/email-studio-entity-preview-bf44
#   bash Repo_abpe/email_studio/incoming/DEPLOY-entity-preview.sh

set -euo pipefail

BACKEND=/opt/abpe/backend
REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/email-studio-entity-preview-bf44}"
BR="origin/${BRANCH}"
R="Repo_abpe/email_studio/incoming"
VENV="${VENV:-$BACKEND/venv311/bin/activate}"

echo "=== Email Studio Entity-Vorschau Deploy ==="
echo "Repo:   $REPO"
echo "Branch: $BRANCH"
echo "Ziel:   $BACKEND"
echo ""

cd "$REPO"
git fetch origin "$BRANCH"

echo "--- Quelldateien kopieren (apps/.../static) ---"
git show "$BR:$R/es-studio.js" \
  > "$BACKEND/apps/abpe_email_studio/static/email_studio/js/es-studio.js"
git show "$BR:$R/es-core.js" \
  > "$BACKEND/apps/abpe_email_studio/static/email_studio/js/es-core.js"

echo "--- collectstatic (staticfiles aktualisieren) ---"
cd "$BACKEND"
# shellcheck disable=SC1090
source "$VENV"
python manage.py collectstatic --noinput

echo ""
echo "--- Prüfung ---"
grep -c "_getEditorSnapshot" "$BACKEND/staticfiles/email_studio/js/es-studio.js"
grep -c "_loadPreview" "$BACKEND/staticfiles/email_studio/js/es-core.js"

echo ""
echo "--- Neustart ---"
supervisorctl restart abpe-django

echo ""
echo "✓ Fertig. Browser: Strg+Shift+R"
