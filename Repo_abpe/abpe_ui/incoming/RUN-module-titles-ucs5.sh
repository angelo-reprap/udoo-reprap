#!/bin/bash
# module.json titles + Portal-Fixes auf ucs5 (ohne git checkout)
#
#   cd /mnt/public/udoo-reprap && git fetch origin cursor/email-studio-undo-i18n-bf44
#   git show origin/cursor/email-studio-undo-i18n-bf44:Repo_abpe/abpe_ui/incoming/RUN-module-titles-ucs5.sh | bash
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
BR="${BR:-origin/cursor/email-studio-undo-i18n-bf44}"
UI="Repo_abpe/abpe_ui/incoming"

cd "$REPO"
git fetch origin cursor/email-studio-undo-i18n-bf44 2>/dev/null || true

echo "=== 1. Translator (mit module.json titles) ==="
git show "$BR:$UI/i18n_translator.py" > "$BACKEND/apps/abpe_ui/bin/i18n_translator.py"

echo "=== 2. Portal JS + Templates ==="
git show "$BR:$UI/core-language.js" \
  > "$BACKEND/apps/abpe_ui/static/abpe_ui/js/core/core-language.js"
git show "$BR:$UI/header.html" \
  > "$BACKEND/apps/abpe_ui/templates/abpe_ui/components/header.html"
git show "$BR:$UI/sidebar.html" \
  > "$BACKEND/apps/abpe_ui/templates/abpe_ui/components/sidebar.html"
git show "$BR:$UI/_nav_link.html" \
  > "$BACKEND/apps/abpe_ui/templates/abpe_ui/components/_nav_link.html"

echo "=== 3. module.json (ohne bogus ar-Platzhalter) ==="
for mod in admin_portal cv_editor cv_upload doc_studio documentation email email_studio matching namazu; do
  git show "$BR:$UI/modules/$mod/module.json" \
    > "$BACKEND/apps/abpe_ui/templates/abpe_ui/modules/$mod/module.json"
  echo "  ✓ $mod"
done

cd "$BACKEND"
source /opt/abpe/venv311/bin/activate 2>/dev/null || true

echo ""
echo "=== 4. Translator — i18n/ + module.json titles ==="
PYTHONWARNINGS=ignore python3 apps/abpe_ui/bin/i18n_translator.py

echo ""
echo "=== 5. Validate ==="
PYTHONWARNINGS=ignore python3 apps/abpe_ui/bin/i18n_validate.py || true

python manage.py collectstatic --noinput
supervisorctl restart abpe-django

echo ""
echo "✓ Fertig — Strg+Shift+R"
echo ""
echo "Neue Sprache (z.B. Ungarisch):"
echo "  mkdir -p apps/abpe_ui/static/abpe_ui/i18n/hu"
echo "  python3 apps/abpe_ui/bin/i18n_translator.py --lang hu"
echo "  python3 apps/abpe_ui/bin/i18n_validate.py --lang hu"
