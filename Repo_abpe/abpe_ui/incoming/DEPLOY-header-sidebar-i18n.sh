#!/bin/bash
# Header + Sidebar i18n Fix (ucs5)
#
# Fixes:
#   - core-language.js: Modul-JSON überschreibt nicht mehr Portal-Keys (help, profile, …)
#   - header.html: Suche mit data-i18n-placeholder
#   - module.json: alle 14 Sprachen in titles
#   - email_studio base.html: sicheres mergeModuleI18n
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/email-studio-undo-i18n-bf44
#   git show origin/cursor/email-studio-undo-i18n-bf44:Repo_abpe/abpe_ui/incoming/DEPLOY-header-sidebar-i18n.sh | bash
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
BRANCH="${BRANCH:-cursor/email-studio-undo-i18n-bf44}"
BR="origin/${BRANCH}"
UI="Repo_abpe/abpe_ui/incoming"
ES="Repo_abpe/email_studio/incoming"

cd "$REPO"
git fetch origin "$BRANCH"

echo "=== Header/Sidebar i18n Fix ==="

# JS
git show "$BR:$UI/core-language.js" > "$BACKEND/apps/abpe_ui/static/abpe_ui/js/core/core-language.js"

# Templates
git show "$BR:$UI/header.html" > "$BACKEND/apps/abpe_ui/templates/abpe_ui/components/header.html"
git show "$BR:$ES/base.html" > "$BACKEND/apps/abpe_ui/templates/abpe_ui/modules/email_studio/base.html"

# module.json — alle Module
for mod in admin_portal cv_editor cv_upload doc_studio documentation email email_studio matching namazu; do
  dest="$BACKEND/apps/abpe_ui/templates/abpe_ui/modules/$mod/module.json"
  if git show "$BR:$UI/modules/$mod/module.json" > /dev/null 2>&1; then
    git show "$BR:$UI/modules/$mod/module.json" > "$dest"
    echo "  ✓ module.json: $mod"
  fi
done

cd "$BACKEND"
source /opt/abpe/venv311/bin/activate 2>/dev/null || true
python manage.py collectstatic --noinput
supervisorctl restart abpe-django

echo ""
echo "✓ Fertig — Strg+Shift+R"
echo ""
echo "Prüfen:"
echo "  1. AR wählen → Header: Hilfe/Profil/Einstellungen auf Arabisch"
echo "  2. Sidebar: Nav-Titel wechseln (DE-Fallback für ar/ja/ko/…)"
echo "  3. Suche-Placeholder übersetzt (Key: search in core-common.json)"
