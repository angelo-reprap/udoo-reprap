#!/usr/bin/env bash
# Email Studio Phase 2 — KI-Wizard UI deploy (ucs5)
# Branch: cursor/email-studio-ki-wizard-phase2-bf44
#
# Voraussetzung: abpe_ki_wiz Phase 1 bereits installiert (/ki-wizard/api/)

set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BR="${BR:-origin/cursor/email-studio-ki-wizard-phase2-bf44}"
R="${REPO}/Repo_abpe/email_studio/incoming"
KI="${REPO}/Repo_abpe/abpe_ki_wiz/incoming"
B="/opt/abpe/backend"

cd "$REPO"
git fetch origin cursor/email-studio-ki-wizard-phase2-bf44 cursor/abpe-ki-wiz-phase0-bf44 2>/dev/null || true

copy() {
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  cp -a "$src" "$dst"
  echo "OK: $dst"
}

# Email Studio UI
copy "$R/studio.html" "$B/apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html"
copy "$R/ki-wizard-modal.html" "$B/apps/abpe_ui/templates/abpe_ui/modules/email_studio/ki-wizard-modal.html"
copy "$R/es-studio.js" "$B/apps/abpe_email_studio/static/email_studio/js/es-studio.js"
copy "$R/es-ki-wizard.js" "$B/apps/abpe_email_studio/static/email_studio/js/es-ki-wizard.js"
copy "$R/mod-email_studio.css" "$B/apps/abpe_ui/static/abpe_ui/css/mod/mod-email_studio.css"

# i18n (de + en minimum; weitere Sprachen aus incoming/i18n/)
for lang in de en fr it es; do
  src="$R/i18n/${lang}/email_studio.json"
  if [[ -f "$src" ]]; then
    copy "$src" "$B/apps/abpe_ui/static/abpe_ui/i18n/${lang}/modules/email_studio/email_studio.json"
  fi
done

# KI-Wizard Backend (falls noch nicht aktuell)
if [[ -d "$KI" ]]; then
  rsync -av --exclude __pycache__ "$KI/" "$B/apps/abpe_ki_wiz/"
  echo "OK: abpe_ki_wiz synced"
fi

supervisorctl restart abpe-django
echo ""
echo "Deploy fertig. Test: /email-studio/studio/ → 4. Karte „KI-Assistent“"
