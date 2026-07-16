#!/bin/bash
# Sidebar + Header über i18n-Translator (ucs5) — KEIN module.json-Patching
#
# Workflow (wie vorgesehen):
#   1. navigation.json in i18n/de/ (Referenz)
#   2. Templates + core-language.js (data-i18n="nav.*")
#   3. i18n_translator.py → alle Sprachen inkl. hu/ar/…
#   4. i18n_validate.py --check
#
# Ohne git checkout — nur git show:
#   cd /mnt/public/udoo-reprap && git fetch origin cursor/email-studio-undo-i18n-bf44
#   git show origin/cursor/email-studio-undo-i18n-bf44:Repo_abpe/abpe_ui/incoming/RUN-navigation-i18n-ucs5.sh | bash
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
BR="${BR:-origin/cursor/email-studio-undo-i18n-bf44}"
UI="Repo_abpe/abpe_ui/incoming"

cd "$REPO"
git fetch origin cursor/email-studio-undo-i18n-bf44 2>/dev/null || true

echo "=== Navigation i18n (Translator-Weg) ==="

# 1. DE-Referenz navigation.json
git show "$BR:$UI/i18n/de/navigation.json" \
  > "$BACKEND/apps/abpe_ui/static/abpe_ui/i18n/de/navigation.json"
echo "  ✓ i18n/de/navigation.json"

# 2. Portal JS + Templates
git show "$BR:$UI/core-language.js" \
  > "$BACKEND/apps/abpe_ui/static/abpe_ui/js/core/core-language.js"
git show "$BR:$UI/header.html" \
  > "$BACKEND/apps/abpe_ui/templates/abpe_ui/components/header.html"
git show "$BR:$UI/sidebar.html" \
  > "$BACKEND/apps/abpe_ui/templates/abpe_ui/components/sidebar.html"
git show "$BR:$UI/_nav_link.html" \
  > "$BACKEND/apps/abpe_ui/templates/abpe_ui/components/_nav_link.html"
echo "  ✓ core-language.js, header, sidebar, _nav_link"

# 3. Translator — fehlende navigation.json in allen Sprachen
cd "$BACKEND"
source /opt/abpe/venv311/bin/activate 2>/dev/null || true
echo ""
echo "=== i18n_translator.py ==="
PYTHONWARNINGS=ignore python3 apps/abpe_ui/bin/i18n_translator.py

echo ""
echo "=== i18n_validate.py (Struktur + Keys) ==="
PYTHONWARNINGS=ignore python3 apps/abpe_ui/bin/i18n_validate.py --check || true

python manage.py collectstatic --noinput
supervisorctl restart abpe-django

echo ""
echo "✓ Fertig — Strg+Shift+R"
echo ""
echo "Neue Sprache (z.B. Ungarisch):"
echo "  mkdir -p apps/abpe_ui/static/abpe_ui/i18n/hu"
echo "  python3 apps/abpe_ui/bin/i18n_translator.py --lang hu"
echo "  python3 apps/abpe_ui/bin/i18n_validate.py --lang hu --check"
