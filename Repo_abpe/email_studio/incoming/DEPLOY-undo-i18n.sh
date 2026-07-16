#!/bin/bash
# Email Studio — i18n + Undo/Milestone (ucs5)
set -euo pipefail

BACKEND=/opt/abpe/backend
REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/email-studio-undo-i18n-bf44}"
BR="origin/${BRANCH}"
R="Repo_abpe/email_studio/incoming"
VENV="${VENV:-$BACKEND/venv311/bin/activate}"

echo "=== Email Studio Undo/i18n Deploy ==="
cd "$REPO"
git fetch origin "$BRANCH"

# Template (nicht collectstatic!)
git show "$BR:$R/studio.html" > "$BACKEND/apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html"

# JS + CSS + API
git show "$BR:$R/es-studio.js" > "$BACKEND/apps/abpe_email_studio/static/email_studio/js/es-studio.js"
git show "$BR:$R/mod-email_studio.css" > "$BACKEND/apps/abpe_ui/static/abpe_ui/css/mod/mod-email_studio.css"
git show "$BR:$R/api.py" > "$BACKEND/apps/abpe_email_studio/api.py"

# i18n kanonisch DE + EN
git show "$BR:$R/email_studio.json" > "$REPO/$R/email_studio.json"
git show "$BR:$R/i18n/en/email_studio.json" > "$REPO/$R/i18n/en/email_studio.json"
git show "$BR:$R/patch_email_studio_i18n.py" > "$REPO/$R/patch_email_studio_i18n.py"
chmod +x "$REPO/$R/patch_email_studio_i18n.py"

echo "--- i18n patchen (alle Sprachen) ---"
python3 "$REPO/$R/patch_email_studio_i18n.py" --backend "$BACKEND" --repo "$REPO"

echo "--- i18n_translator (Deepseek) ---"
cd "$BACKEND"
source "$VENV"
if [[ -f apps/abpe_crm/bin/i18n_translator.py ]]; then
  python apps/abpe_crm/bin/i18n_translator.py || echo "WARN: i18n_translator fehlgeschlagen — manuell nachholen"
else
  echo "WARN: i18n_translator.py nicht gefunden — nur DE/EN-Merge aktiv"
fi

python manage.py collectstatic --noinput
supervisorctl restart abpe-django
echo "✓ Fertig — Strg+Shift+R"
