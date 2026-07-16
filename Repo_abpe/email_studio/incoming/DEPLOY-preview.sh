#!/bin/bash
# Email Studio — Dummy-Vorschau deployen (ucs5)
# Ausführen: bash DEPLOY-preview.sh
# Oder von ucs5:
#   cd /mnt/public/udoo-reprap && git fetch origin cursor/email-studio-dummy-preview-bf44
#   bash Repo_abpe/email_studio/incoming/DEPLOY-preview.sh

set -euo pipefail

BACKEND=/opt/abpe/backend
REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/email-studio-dummy-preview-bf44}"
BR="origin/${BRANCH}"
R="Repo_abpe/email_studio/incoming"

echo "=== Email Studio Dummy-Vorschau Deploy ==="
echo "Repo:   $REPO"
echo "Branch: $BRANCH"
echo "Ziel:   $BACKEND"
echo ""

cd "$BACKEND"

NOTE="Dummy-Vorschau $(date +%Y-%m-%d)"
echo "--- Backup ---"
python3 Archiv/backup_restore.py -save apps/abpe_email_studio/api.py -m "$NOTE"
python3 Archiv/backup_restore.py -save apps/abpe_email_studio/services/renderer.py -m "$NOTE"
python3 Archiv/backup_restore.py -save apps/abpe_email_studio/static/email_studio/js/es-studio.js -m "$NOTE"
python3 Archiv/backup_restore.py -save apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html -m "$NOTE"
python3 Archiv/backup_restore.py -save apps/abpe_ui/static/abpe_ui/css/mod/mod-email_studio.css -m "$NOTE"
python3 Archiv/backup_restore.py -save apps/abpe_ui/static/abpe_ui/i18n/de/modules/email_studio/email_studio.json -m "$NOTE"

echo ""
echo "--- Fetch ---"
git -C "$REPO" fetch origin "$BRANCH"

echo ""
echo "--- Deploy (git show) ---"
git -C "$REPO" show "$BR:$R/api.py" \
  > "$BACKEND/apps/abpe_email_studio/api.py"
git -C "$REPO" show "$BR:$R/renderer.py" \
  > "$BACKEND/apps/abpe_email_studio/services/renderer.py"
git -C "$REPO" show "$BR:$R/es-studio.js" \
  > "$BACKEND/apps/abpe_email_studio/static/email_studio/js/es-studio.js"
git -C "$REPO" show "$BR:$R/studio.html" \
  > "$BACKEND/apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html"
git -C "$REPO" show "$BR:$R/mod-email_studio.css" \
  > "$BACKEND/apps/abpe_ui/static/abpe_ui/css/mod/mod-email_studio.css"
git -C "$REPO" show "$BR:$R/email_studio.json" \
  > "$BACKEND/apps/abpe_ui/static/abpe_ui/i18n/de/modules/email_studio/email_studio.json"

echo ""
echo "--- Prüfsummen (neu vs. Backup sollten unterschiedlich sein) ---"
md5sum apps/abpe_email_studio/api.py
md5sum apps/abpe_email_studio/static/email_studio/js/es-studio.js
grep -c "preview_refresh\|render_preview\|allow-same-origin" \
  apps/abpe_email_studio/api.py \
  apps/abpe_email_studio/static/email_studio/js/es-studio.js \
  apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html || true

echo ""
echo "--- Neustart ---"
supervisorctl restart abpe-django

echo ""
echo "✓ Fertig. Browser: Strg+Shift+R auf /email-studio/studio/?template=13"
echo "  Erwartung: Badge 'Beispieldaten', Button 'Aktualisieren', keine {termin_datum}"
