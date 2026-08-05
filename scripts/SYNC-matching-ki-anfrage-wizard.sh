#!/usr/bin/env bash
# Repo → Live: abpe_ki_wiz + Matching-UI (KI-Anfragen-Wizard)
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap && git fetch origin
#   bash scripts/SYNC-matching-ki-anfrage-wizard.sh
#
# Danach:
#   cd /opt/abpe/backend && /opt/abpe/venv311/bin/python manage.py sync_wizard_prompts --wizard-id matching_anfrage
#   supervisorctl restart abpe-django
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-origin/cursor/matching-ki-anfrage-wizard-7f07}"
LIVE_KI="${LIVE_KI:-/opt/abpe/backend/apps/abpe_ki_wiz}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
STATICFILES="${STATICFILES:-/opt/abpe/backend/staticfiles}"

cd "$REPO"
git fetch origin cursor/matching-ki-anfrage-wizard-7f07 || true

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git archive "$BRANCH" \
  Repo_abpe/abpe_ki_wiz/incoming \
  Repo_abpe/abpe_ui/incoming/mod-matching.js \
  | tar -x -C "$TMP"

# ── abpe_ki_wiz (kein --delete: Live kann zusätzliche Dateien haben) ─────────
mkdir -p "$LIVE_KI"
rsync -a \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "$TMP/Repo_abpe/abpe_ki_wiz/incoming/" \
  "$LIVE_KI/"
echo "OK — abpe_ki_wiz → $LIVE_KI"

# ── Matching UI ──────────────────────────────────────────────────────────────
mkdir -p "$LIVE_UI/static/abpe_ui/js/mod"
cp -a "$TMP/Repo_abpe/abpe_ui/incoming/mod-matching.js" \
  "$LIVE_UI/static/abpe_ui/js/mod/mod-matching.js"
echo "OK — mod-matching.js → $LIVE_UI/static/abpe_ui/js/mod/"

if [[ -d "$STATICFILES" ]]; then
  mkdir -p "$STATICFILES/abpe_ui/js/mod"
  cp -a "$LIVE_UI/static/abpe_ui/js/mod/mod-matching.js" \
    "$STATICFILES/abpe_ui/js/mod/mod-matching.js"
  echo "OK — auch nach $STATICFILES/abpe_ui/js/mod/ kopiert"
fi

echo
echo "Prompts in DB (falls noch nicht):"
echo "  cd /opt/abpe/backend && /opt/abpe/venv311/bin/python manage.py sync_wizard_prompts --wizard-id matching_anfrage"
echo "  # Prompt-Text aktualisieren: … sync_wizard_prompts --wizard-id matching_anfrage --force"
echo
echo "Restart:"
echo "  supervisorctl restart abpe-django"
echo
echo "UI: Matching → Tab „Neue Anfrage“ → Button links neben „+ Neue Anfrage“"
echo "API: POST /ki-wizard/api/matching-anfrage/extract/"
