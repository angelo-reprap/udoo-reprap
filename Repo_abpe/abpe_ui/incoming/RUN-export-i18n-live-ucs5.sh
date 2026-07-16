#!/bin/bash
# Live i18n + Sprach-Dropdown → Repo_abpe/incoming (ucs5)
#
# Voraussetzung: export-to-repo.sh installiert (siehe Repo_abpe/README.md)
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/portal-export-script-bf44
#   mkdir -p /opt/abpe/scripts
#   for f in export-to-repo.sh export-portal-baseline.sh; do
#     git show origin/cursor/portal-export-script-bf44:scripts/$f > /opt/abpe/scripts/$f
#     chmod +x /opt/abpe/scripts/$f
#   done
#
# Dann:
#   bash Repo_abpe/abpe_ui/incoming/RUN-export-i18n-live-ucs5.sh
#   cd /mnt/public/udoo-reprap && git add Repo_abpe/ && git commit -m "Live: i18n + lang dropdown" && git push

set -euo pipefail

BACKEND="${ABPE_BACKEND:-/opt/abpe/backend}"
EXPORT="${ABPE_EXPORT_SH:-/opt/abpe/scripts/export-to-repo.sh}"
REPO="${REPO:-/mnt/public/udoo-reprap}"

if [[ ! -x "$EXPORT" ]]; then
  echo "Fehler: $EXPORT nicht gefunden. Zuerst export-to-repo.sh installieren." >&2
  exit 1
fi

echo "=== Portal i18n + Dropdown ==="
"$EXPORT" abpe_ui \
  "$BACKEND/apps/abpe_ui/templates/abpe_ui/base.html" \
  "$BACKEND/apps/abpe_ui/templates/abpe_ui/components/header.html" \
  "$BACKEND/apps/abpe_ui/templates/abpe_ui/components/sidebar.html" \
  "$BACKEND/apps/abpe_ui/templates/abpe_ui/components/_nav_link.html" \
  "$BACKEND/apps/abpe_ui/static/abpe_ui/js/core/core-language.js" \
  "$BACKEND/apps/abpe_ui/static/abpe_ui/js/core/core-lang-dropdown.js" \
  "$BACKEND/apps/abpe_ui/bin/i18n_translator.py"

echo ""
echo "=== CRM Sprach-Dropdown (Referenz) ==="
"$EXPORT" abpe_crm \
  "$BACKEND/apps/abpe_crm/templates/abpe_crm/base.html" \
  "$BACKEND/apps/abpe_crm/templates/abpe_crm/components/header.html" \
  "$BACKEND/apps/abpe_crm/static/abpe_crm/js/core-language.js" \
  "$BACKEND/apps/abpe_crm/static/abpe_crm/js/core-crm-lang-dropdown.js"

echo ""
echo "=== module.json (Sidebar titles) ==="
for f in "$BACKEND"/apps/abpe_ui/templates/abpe_ui/modules/*/module.json; do
  mod=$(basename "$(dirname "$f")")
  mkdir -p "/mnt/public/Repo_abpe/abpe_ui/incoming/modules/${mod}"
  cp -a "$f" "/mnt/public/Repo_abpe/abpe_ui/incoming/modules/${mod}/module.json"
  echo "OK: module.json → ${mod}"
done

echo ""
echo "=== Fertig. Nächster Schritt ==="
echo "  cd $REPO"
echo "  git add Repo_abpe/abpe_ui/incoming/ Repo_abpe/abpe_crm/incoming/"
echo "  git commit -m 'Live: i18n lang dropdown + module titles'"
echo "  git push"
echo ""
echo "Dann Cloud Agent: 'Bitte Repo_abpe analysieren'"
