#!/usr/bin/env bash
# Optional: Dateien aus Repo-Branch nach Live rsyncen (Register bleibt manuell).
set -euo pipefail
REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-origin/cursor/abpe-shaduler-scaffold-7f07}"
LIVE_APP="${LIVE_APP:-/opt/abpe/backend/apps/abpe_shaduler}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"

cd "$REPO"
git fetch origin cursor/abpe-shaduler-scaffold-7f07 || true

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git archive "$BRANCH" Repo_abpe/abpe_shaduler/incoming Repo_abpe/abpe_ui/incoming | tar -x -C "$TMP"

mkdir -p "$LIVE_APP"
rsync -a --delete \
  "$TMP/Repo_abpe/abpe_shaduler/incoming/" \
  "$LIVE_APP/"

mkdir -p "$LIVE_UI/templates/abpe_ui/modules/shaduler"
cp -a "$TMP/Repo_abpe/abpe_ui/incoming/modules/shaduler/module.json" \
  "$LIVE_UI/templates/abpe_ui/modules/shaduler/module.json"

mkdir -p "$LIVE_UI/static/abpe_ui/css/mod" "$LIVE_UI/static/abpe_ui/js/mod"
cp -a "$TMP/Repo_abpe/abpe_ui/incoming/mod-shaduler.css" \
  "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css"
cp -a "$TMP/Repo_abpe/abpe_ui/incoming/mod-shaduler.js" \
  "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js"
cp -a "$TMP/Repo_abpe/abpe_ui/incoming/mod-shaduler-kalender.js" \
  "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler-kalender.js"

for lang in de en; do
  mkdir -p "$LIVE_UI/static/abpe_ui/i18n/$lang/modules/shaduler"
  cp -a "$TMP/Repo_abpe/abpe_ui/incoming/i18n/$lang/modules/shaduler/." \
    "$LIVE_UI/static/abpe_ui/i18n/$lang/modules/shaduler/"
done

echo "OK — Dateien sync. Jetzt nano laut Repo_abpe/abpe_shaduler/SETUP_NANO.md"
echo "  apps.py  → 'apps.abpe_shaduler'"
echo "  urls.py  → path('shaduler/', include(...))"
