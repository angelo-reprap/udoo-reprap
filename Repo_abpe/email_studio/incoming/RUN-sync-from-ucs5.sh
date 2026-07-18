#!/usr/bin/env bash
# ucs5 Live → Repo_abpe/email_studio/incoming (Sicherungs-Sync vor Phase-2-Arbeit)
#
# Auf ucs5 ausführen:
#   cd /mnt/public/udoo-reprap && git pull
#   bash Repo_abpe/email_studio/incoming/RUN-sync-from-ucs5.sh
#
# Umgebung (optional):
#   ABPE_BACKEND=/opt/abpe/backend
#   REPO=/mnt/public/udoo-reprap

set -euo pipefail

BE="${ABPE_BACKEND:-/opt/abpe/backend}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
STAGING="${REPO}/Repo_abpe/email_studio/incoming"
KI_STAGING="${REPO}/Repo_abpe/abpe_ki_wiz/incoming"

mkdir -p "$STAGING" "$KI_STAGING"

rsync -av --exclude '__pycache__' --exclude '*.pyc' \
  "${BE}/apps/abpe_email_studio/" \
  "$STAGING/" \
  --include='*.py' --include='*.html' --include='*.js' --include='*.css' --include='*.json' \
  --include='signatures/**' --include='*/' --exclude='*'

# UI-Templates (Portal)
UI_TPL="${BE}/apps/abpe_ui/templates/abpe_ui/modules/email_studio"
if [[ -d "$UI_TPL" ]]; then
  rsync -av "$UI_TPL/" "$STAGING/" --include='*.html' --exclude='*'
fi

# Static JS/CSS → incoming (Staging-Namen)
ES_JS="${BE}/apps/abpe_email_studio/static/email_studio/js"
if [[ -d "$ES_JS" ]]; then
  rsync -av "$ES_JS/" "$STAGING/" --include='*.js' --exclude='*'
fi

ES_CSS="${BE}/apps/abpe_ui/static/abpe_ui/css/mod"
for f in mod-email_studio.css mod-es-components.css mod-email_studio-delta.css; do
  [[ -f "${ES_CSS}/${f}" ]] && cp -a "${ES_CSS}/${f}" "$STAGING/"
done

# i18n (alle Sprachen)
I18N_ROOT="${BE}/apps/abpe_ui/static/abpe_ui/i18n"
if [[ -d "$I18N_ROOT" ]]; then
  for lang in "$I18N_ROOT"/*/; do
    code="$(basename "$lang")"
    src="${lang}modules/email_studio/email_studio.json"
    if [[ -f "$src" ]]; then
      mkdir -p "${STAGING}/i18n/${code}"
      cp -a "$src" "${STAGING}/i18n/${code}/email_studio.json"
    fi
  done
fi

# KI-Wizard (falls auf ucs5 installiert)
if [[ -d "${BE}/apps/abpe_ki_wiz" ]]; then
  rsync -av --exclude '__pycache__' \
    "${BE}/apps/abpe_ki_wiz/" "$KI_STAGING/"
fi

echo ""
echo "OK: Sync nach ${STAGING}"
echo "    KI-Wiz: ${KI_STAGING}"
echo "Nächster Schritt: git diff, commit, push"
