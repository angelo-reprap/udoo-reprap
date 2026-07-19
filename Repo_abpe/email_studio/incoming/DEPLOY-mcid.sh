#!/usr/bin/env bash
# MCID — Modul/Block-Renderer + Editor + KI-Vorschläge (ucs5)
# Branch: cursor/email-studio-consolidate-modules-7f07
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/email-studio-consolidate-modules-7f07
#   git checkout cursor/email-studio-consolidate-modules-7f07
#   git pull origin cursor/email-studio-consolidate-modules-7f07
#   bash Repo_abpe/email_studio/incoming/DEPLOY-mcid.sh

set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BR_NAME="${BR_NAME:-cursor/email-studio-consolidate-modules-7f07}"
BR="${BR:-origin/${BR_NAME}}"
R="Repo_abpe/email_studio/incoming"
KI="Repo_abpe/abpe_ki_wiz/incoming"
B="/opt/abpe/backend"
NOTE="${NOTE:-MCID Deploy $(date +%Y-%m-%d)}"

cd "$REPO"
git fetch origin "$BR_NAME"
git checkout "$BR_NAME" 2>/dev/null || git checkout -b "$BR_NAME" "origin/$BR_NAME"
git pull origin "$BR_NAME" || true

show() {
  local repo_path="$1" live_path="$2"
  mkdir -p "$(dirname "$live_path")"
  git show "${BR}:${repo_path}" > "$live_path"
  echo "OK: $live_path"
}

backup() {
  local rel="$1"
  if [[ -f "$B/$rel" ]]; then
    (cd "$B" && python3 Archiv/backup_restore.py -save "$rel" -m "$NOTE") || true
  else
    echo "SKIP backup (neu): $rel"
  fi
}

echo "=== 1/4 Backup ==="
backup apps/abpe_email_studio/api.py
backup apps/abpe_email_studio/urls.py
backup apps/abpe_email_studio/services/renderer.py
backup apps/abpe_email_studio/services/mcid_validator.py
backup apps/abpe_email_studio/blocks_registry.py
backup apps/abpe_email_studio/static/email_studio/js/es-studio.js
backup apps/abpe_email_studio/static/email_studio/js/es-ki-wizard.js
backup apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html
backup apps/abpe_ui/templates/abpe_ui/modules/email_studio/ki-wizard-modal.html
backup apps/abpe_ui/static/abpe_ui/css/mod/mod-email_studio.css
backup apps/abpe_ui/static/abpe_ui/i18n/de/modules/email_studio/email_studio.json
backup apps/abpe_ui/static/abpe_ui/i18n/en/modules/email_studio/email_studio.json
backup apps/abpe_ki_wiz/providers/email_template.py
backup apps/abpe_ki_wiz/services/orchestrator.py
backup apps/abpe_ki_wiz/services/validator.py
backup apps/abpe_ki_wiz/prompt_defaults.py
backup apps/abpe_ki_wiz/questions/email_template.json

echo "=== 2/4 Email Studio kopieren ==="
show "$R/api.py"            "$B/apps/abpe_email_studio/api.py"
show "$R/urls.py"           "$B/apps/abpe_email_studio/urls.py"
show "$R/blocks_registry.py" "$B/apps/abpe_email_studio/blocks_registry.py"
show "$R/services/renderer.py" "$B/apps/abpe_email_studio/services/renderer.py"
show "$R/services/mcid_validator.py" "$B/apps/abpe_email_studio/services/mcid_validator.py"
show "$R/static/email_studio/js/es-studio.js" "$B/apps/abpe_email_studio/static/email_studio/js/es-studio.js"
show "$R/static/email_studio/js/es-ki-wizard.js" "$B/apps/abpe_email_studio/static/email_studio/js/es-ki-wizard.js"
show "$R/studio.html"       "$B/apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html"
show "$R/ki-wizard-modal.html" "$B/apps/abpe_ui/templates/abpe_ui/modules/email_studio/ki-wizard-modal.html"
show "$R/mod-email_studio.css" "$B/apps/abpe_ui/static/abpe_ui/css/mod/mod-email_studio.css"
show "$R/i18n/de/email_studio.json" "$B/apps/abpe_ui/static/abpe_ui/i18n/de/modules/email_studio/email_studio.json"
show "$R/i18n/en/email_studio.json" "$B/apps/abpe_ui/static/abpe_ui/i18n/en/modules/email_studio/email_studio.json"

echo "=== 3/4 KI-Wiz katalog/prompt/renderer-hooks ==="
show "$KI/providers/email_template.py" "$B/apps/abpe_ki_wiz/providers/email_template.py"
show "$KI/services/orchestrator.py"    "$B/apps/abpe_ki_wiz/services/orchestrator.py"
show "$KI/services/validator.py"       "$B/apps/abpe_ki_wiz/services/validator.py"
show "$KI/prompt_defaults.py"          "$B/apps/abpe_ki_wiz/prompt_defaults.py"
show "$KI/questions/email_template.json" "$B/apps/abpe_ki_wiz/questions/email_template.json"

echo "=== 4/5 Prompts sync + Header-Seed + Restart ==="
if [[ -f "$B/manage.py" ]]; then
  (
    cd "$B"
    # shellcheck disable=SC1091
    source /opt/abpe/venv311/bin/activate
    python manage.py sync_wizard_prompts --force --wizard-id email_template
    # Modul Header Blau + Adresse in DB
    if [[ -f "$REPO/Repo_abpe/email_studio/incoming/seed_header_adresse.py" ]]; then
      python manage.py shell < "$REPO/Repo_abpe/email_studio/incoming/seed_header_adresse.py" \
        || echo "WARN: seed_header_adresse fehlgeschlagen"
    fi
  ) || echo "WARN: sync_wizard_prompts fehlgeschlagen — manuell prüfen"
else
  echo "WARN: manage.py fehlt"
fi

echo "=== Smoke ==="
grep -n "_paired_block_re\|blocks_registry\|_fill_content_slot" \
  "$B/apps/abpe_email_studio/services/renderer.py" | head
grep -n "LIST_BULLET\|_html_to_plain\|fmt_trenner\|block_anhaenge" \
  "$B/apps/abpe_email_studio/blocks_registry.py" | head
grep -n "es-ki-layout-suggestions\|layout_suggestions" \
  "$B/apps/abpe_email_studio/static/email_studio/js/es-ki-wizard.js" | head
grep -n "justifyLeft\|insertUnorderedList" \
  "$B/apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html" | head
grep -n "font-size: 14px" \
  "$B/apps/abpe_ui/static/abpe_ui/css/mod/mod-email_studio.css" | head -3
# Pflicht: Paar-Regex darf Header nicht bis {{/block}} fressen
grep -q "_paired_block_re" "$B/apps/abpe_email_studio/services/renderer.py" \
  || { echo "FAIL: _paired_block_re fehlt im Live-Renderer"; exit 1; }
grep -q "_html_to_plain" "$B/apps/abpe_email_studio/blocks_registry.py" \
  || { echo "FAIL: _html_to_plain fehlt"; exit 1; }
grep -q "McidValidator\|_initMcidValidate\|mcid-validate" \
  "$B/apps/abpe_email_studio/services/mcid_validator.py" \
  "$B/apps/abpe_email_studio/static/email_studio/js/es-studio.js" \
  "$B/apps/abpe_email_studio/urls.py" \
  || { echo "FAIL: MCID-Validator nicht vollständig deployed"; exit 1; }
grep -q "FORMAT_MODULE_ORDER\|Abschnitt hinzufügen" \
  "$B/apps/abpe_email_studio/blocks_registry.py" \
  "$B/apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html" \
  || { echo "FAIL: Sortierung/Abschnitt-UI fehlt"; exit 1; }

supervisorctl restart abpe-django
echo ""
echo "MCID-Deploy fertig. Browser: Strg+Shift+R"
echo "Test: Sidebar Format-Reihenfolge · Button „MCID prüfen“ · Abschnitte"
