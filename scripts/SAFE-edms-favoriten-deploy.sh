#!/usr/bin/env bash
# Deploy EDMS-Favoriten (UI) nach ucs5. Live-Backup, dann gezielte Dateien.
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin && git pull origin cursor/matching-templates-dms-ee01
#   bash scripts/SAFE-edms-favoriten-deploy.sh
#   Browser: Ctrl+F5 auf /crm/dms/
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
LIVE_CRM="${LIVE_CRM:-/opt/abpe/backend/apps/abpe_crm}"
STATICFILES="${STATICFILES:-/opt/abpe/backend/staticfiles}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/abpe/backups}"
TS=$(date +%Y%m%d-%H%M%S)
BAK="$BACKUP_ROOT/edms-favoriten-deploy-$TS"
SRC="$REPO/Repo_abpe/abpe_crm/incoming"

must=(
  templates/abpe_crm/tabs/edms_tab.html
  static/abpe_crm/js/mod-edms.js
  static/abpe_crm/css/mod-edms.css
  static/abpe_crm/i18n/de/modules/crm_edms/crm_dms.json
  static/abpe_crm/i18n/en/modules/crm_edms/crm_dms.json
)
for f in "${must[@]}"; do
  [[ -f "$SRC/$f" ]] || { echo "FAIL fehlt: $SRC/$f"; exit 1; }
done
grep -q "setFavTab" "$SRC/static/abpe_crm/js/mod-edms.js" \
  || { echo "FAIL: mod-edms.js ohne Favoriten"; exit 1; }
grep -q "edms-btn-favoriten" "$SRC/templates/abpe_crm/tabs/edms_tab.html" \
  || { echo "FAIL: edms_tab.html ohne Favoriten-Schalter"; exit 1; }

mkdir -p "$BAK"
echo "Backup → $BAK"

deploy_one() {
  local rel="$1"
  local src="$SRC/$rel"
  local dst="$LIVE_CRM/$rel"
  mkdir -p "$(dirname "$dst")" "$BAK/$(dirname "$rel")"
  if [[ -f "$dst" ]]; then
    cp -a "$dst" "$BAK/$rel"
  fi
  cp -a "$src" "$dst"
  echo "OK $rel → $dst"
  local sf="$STATICFILES/${rel#static/}"
  if [[ "$rel" == static/* && -d "$STATICFILES" ]]; then
    mkdir -p "$(dirname "$sf")"
    cp -a "$src" "$sf"
    echo "OK staticfiles $(basename "$sf")"
  fi
}

for f in "${must[@]}"; do
  deploy_one "$f"
done

echo
echo "Deploy fertig. Backup: $BAK"
echo "  Browser Ctrl+F5 → /crm/dms/ → nach Personen → Favoriten"
echo "Restore: cp -a $BAK/static/abpe_crm/js/mod-edms.js $LIVE_CRM/static/abpe_crm/js/mod-edms.js"
