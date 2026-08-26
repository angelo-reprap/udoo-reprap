#!/usr/bin/env bash
# Deploy Matching Gulp/FLM-Merge (Join + Backoffice) — mit Backup.
#
# ucs5:
#   cd /mnt/public/udoo-reprap
#   git pull origin cursor/matching-shortlist-weights-1532
#   bash scripts/SAFE-matching-sources-merge-prep.sh          # Backup + Diff
#   bash scripts/SAFE-matching-sources-merge-deploy.sh
#   supervisorctl restart abpe-django abpe-celery
#   # Browser Ctrl+F5 → Shortlist → Erneut matchen
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
LIVE_MW="${LIVE_MW:-/opt/abpe/backend/apps/abpe_matching_workflow}"
LIVE_SH="${LIVE_SH:-/opt/abpe/backend/apps/abpe_shaduler}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
STATICFILES="${STATICFILES:-/opt/abpe/backend/staticfiles}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/abpe/backups}"
TS=$(date +%Y%m%d-%H%M%S)
BAK="$BACKUP_ROOT/matching-sources-merge-deploy-$TS"

SRC_MW="$REPO/Repo_abpe/abpe_matching_workflow/incoming"
SRC_SH="$REPO/Repo_abpe/abpe_shaduler/incoming"
SRC_UI="$REPO/Repo_abpe/abpe_ui/incoming/mod-matching.js"

[[ -d "$SRC_MW/services" ]] || { echo "FAIL: $SRC_MW"; exit 1; }

for f in \
  services/matching_engine.py \
  services/matching_source_join.py \
  services/matching_external_recall.py \
  services/matching_service.py \
  services/outreach_wizard.py \
  views.py urls.py tasks.py
do
  [[ -f "$SRC_MW/$f" ]] || { echo "FAIL fehlt: $SRC_MW/$f"; exit 1; }
done
grep -q "matching_external_recall" "$SRC_MW/services/matching_engine.py" \
  || { echo "FAIL: Engine ohne external_recall"; exit 1; }
grep -q "store_backoffice_on_project" "$SRC_MW/services/matching_engine.py" \
  || { echo "FAIL: Engine ohne store_backoffice_on_project"; exit 1; }
grep -q "ext_by_consultant" "$SRC_MW/services/matching_engine.py" \
  || { echo "FAIL: Engine ohne Gulp/FLM-Enrichment (ext_by_consultant)"; exit 1; }
grep -q "already_in_db" "$SRC_MW/services/matching_external_recall.py" \
  || { echo "FAIL: external_recall ohne already_in_db"; exit 1; }
grep -q "filterShortlistSource" "$SRC_UI" \
  || { echo "FAIL: UI ohne filterShortlistSource"; exit 1; }
grep -q "shortlist-backoffice" "$SRC_UI" \
  || { echo "FAIL: UI ohne Backoffice-Block"; exit 1; }
grep -q "DEFAULT_MAX_EXTERNAL_HITS" "$SRC_MW/services/matching_external_recall.py" \
  || { echo "FAIL: external_recall ohne DEFAULT_MAX_EXTERNAL_HITS (100)"; exit 1; }
grep -q "schwerpunkt" "$SRC_MW/views.py" \
  || { echo "FAIL: views ohne Schwerpunkt-Enrichment"; exit 1; }
grep -q "HTML-Profil" "$SRC_UI" \
  || { echo "FAIL: UI ohne HTML-Profil-Button"; exit 1; }
grep -q "r.schwerpunkt" "$SRC_UI" \
  || { echo "FAIL: UI ohne Schwerpunkt-Zeile"; exit 1; }
grep -q "toggleGenerateExternalList" "$SRC_UI" \
  || { echo "FAIL: UI ohne Gulp/FLM Listen-Schalter"; exit 1; }
grep -q "outreachSelectTemplate" "$SRC_UI" \
  || { echo "FAIL: UI ohne Email-Studio Template-Auswahl"; exit 1; }
grep -q "outreachSetDefaultTemplate" "$SRC_UI" \
  || { echo "FAIL: UI ohne Als Standard setzen"; exit 1; }
grep -q "matching_outreach_default_template_v1" "$SRC_UI" \
  || { echo "FAIL: UI ohne localStorage Standard-Vorlage"; exit 1; }
grep -q "matching_present_to_client" "$SRC_UI" \
  || { echo "FAIL: UI ohne Interesse-Vorlage matching_present_to_client"; exit 1; }
grep -q "stageTemplateMissing" "$SRC_UI" \
  || { echo "FAIL: UI ohne stageTemplateMissing-Hinweis"; exit 1; }
grep -q "outreachSelectSignature" "$SRC_UI" \
  || { echo "FAIL: UI ohne Signatur-Auswahl"; exit 1; }
grep -q "why_short" "$SRC_MW/services/outreach_wizard.py" \
  || { echo "FAIL: outreach_wizard ohne why_short"; exit 1; }
grep -q "project_details" "$SRC_MW/services/outreach_wizard.py" \
  || { echo "FAIL: outreach_wizard ohne project_details"; exit 1; }
grep -q "_redact_customer_names" "$SRC_MW/services/outreach_wizard.py" \
  || { echo "FAIL: outreach_wizard ohne Firmennamen-Redaktion"; exit 1; }
grep -q "api_outreach_email_templates" "$SRC_MW/views.py" \
  || { echo "FAIL: views ohne outreach email-templates API"; exit 1; }
grep -q "outreach/email-templates" "$SRC_MW/urls.py" \
  || { echo "FAIL: urls ohne outreach/email-templates"; exit 1; }
grep -q "DEFAULT_OUTREACH_TEMPLATE" "$SRC_MW/services/outreach_wizard.py" \
  || { echo "FAIL: outreach_wizard ohne DEFAULT_OUTREACH_TEMPLATE"; exit 1; }
grep -q "api_aufgaben_bulk_create" "$REPO/Repo_abpe/abpe_shaduler/incoming/views.py" \
  || { echo "FAIL: Shaduler ohne bulk Aufgaben-API"; exit 1; }
grep -q "aufgaben/bulk" "$REPO/Repo_abpe/abpe_shaduler/incoming/urls.py" \
  || { echo "FAIL: urls ohne aufgaben/bulk"; exit 1; }

mkdir -p "$BAK"/{mw,sh,ui}
echo "Backup → $BAK"

deploy_one() {
  local src="$1" dst="$2" bakdir="$3"
  mkdir -p "$(dirname "$dst")" "$bakdir"
  if [[ -f "$dst" ]]; then
    cp -a "$dst" "$bakdir/$(basename "$dst")"
  fi
  cp -a "$src" "$dst"
  echo "OK $(basename "$src") → $dst"
}

deploy_one "$SRC_MW/services/matching_engine.py" "$LIVE_MW/services/matching_engine.py" "$BAK/mw"
deploy_one "$SRC_MW/services/matching_source_join.py" "$LIVE_MW/services/matching_source_join.py" "$BAK/mw"
deploy_one "$SRC_MW/services/matching_external_recall.py" "$LIVE_MW/services/matching_external_recall.py" "$BAK/mw"
deploy_one "$SRC_MW/services/matching_service.py" "$LIVE_MW/services/matching_service.py" "$BAK/mw"
deploy_one "$SRC_MW/services/outreach_wizard.py" "$LIVE_MW/services/outreach_wizard.py" "$BAK/mw"
deploy_one "$SRC_MW/views.py" "$LIVE_MW/views.py" "$BAK/mw"
deploy_one "$SRC_MW/urls.py" "$LIVE_MW/urls.py" "$BAK/mw"
deploy_one "$SRC_MW/tasks.py" "$LIVE_MW/tasks.py" "$BAK/mw"

# Shortlist-Reset + Aufgaben-Bulk (Wiedervorlagen-Gruppen)
LIVE_SH_ROOT="${LIVE_SH%/services}"
if [[ -f "$REPO/Repo_abpe/abpe_shaduler/incoming/views.py" && -d "$LIVE_SH_ROOT" ]]; then
  deploy_one "$REPO/Repo_abpe/abpe_shaduler/incoming/views.py" "$LIVE_SH_ROOT/views.py" "$BAK/sh"
fi
if [[ -f "$REPO/Repo_abpe/abpe_shaduler/incoming/urls.py" && -d "$LIVE_SH_ROOT" ]]; then
  deploy_one "$REPO/Repo_abpe/abpe_shaduler/incoming/urls.py" "$LIVE_SH_ROOT/urls.py" "$BAK/sh"
fi
if [[ -f "$REPO/Repo_abpe/abpe_shaduler/incoming/services/aufgaben_service.py" ]]; then
  deploy_one "$REPO/Repo_abpe/abpe_shaduler/incoming/services/aufgaben_service.py" \
    "$LIVE_SH/services/aufgaben_service.py" "$BAK/sh"
fi

# Gulp/FLM search_term/query (falls Repo neuer)
if [[ -f "$SRC_SH/services/radar_berater_gulp.py" ]]; then
  deploy_one "$SRC_SH/services/radar_berater_gulp.py" "$LIVE_SH/services/radar_berater_gulp.py" "$BAK/sh"
fi
if [[ -f "$SRC_SH/services/radar_berater_fl.py" ]]; then
  deploy_one "$SRC_SH/services/radar_berater_fl.py" "$LIVE_SH/services/radar_berater_fl.py" "$BAK/sh"
fi

SRC_UI_SH="$REPO/Repo_abpe/abpe_ui/incoming/mod-shaduler.js"
mkdir -p "$LIVE_UI/static/abpe_ui/js/mod"
deploy_one "$SRC_UI" "$LIVE_UI/static/abpe_ui/js/mod/mod-matching.js" "$BAK/ui"
if [[ -f "$SRC_UI_SH" ]]; then
  deploy_one "$SRC_UI_SH" "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js" "$BAK/ui"
fi
if [[ -d "$STATICFILES/abpe_ui/js/mod" ]]; then
  deploy_one "$SRC_UI" "$STATICFILES/abpe_ui/js/mod/mod-matching.js" "$BAK/ui"
  if [[ -f "$SRC_UI_SH" ]]; then
    deploy_one "$SRC_UI_SH" "$STATICFILES/abpe_ui/js/mod/mod-shaduler.js" "$BAK/ui"
  fi
fi

find "$LIVE_MW" "$LIVE_SH" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

echo
echo "Deploy fertig. Backup: $BAK"
echo "  supervisorctl restart abpe-django abpe-celery"
echo "  Browser Ctrl+F5 → Shortlist → Erneut matchen"
echo "Erwartung: Gulp/FLM je ≤100, Schwerpunkt, HTML-Button, Schalter→Wiedervorlagen-Gruppe"
echo "Restore: cp -a $BAK/mw/* $LIVE_MW/services/  (und views/tasks aus $BAK/mw)"
