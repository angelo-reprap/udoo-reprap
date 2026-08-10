#!/usr/bin/env bash
# Repo → Live: überschreibt abpe_shaduler (+ ausgewählte Shaduler-UI-Dateien).
# rsync --delete auf LIVE_APP — Live-only migrations/0*.py bleiben (P-Filter).
# Berührt NICHT ingest_email / andere Apps. Für ingest_email → Repo: PULL-ingest-email-from-live.sh
set -euo pipefail
REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-origin/cursor/posteingang-index-3min-7f07}"
LIVE_APP="${LIVE_APP:-/opt/abpe/backend/apps/abpe_shaduler}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"

cd "$REPO"
git fetch origin cursor/posteingang-index-3min-7f07 || true

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git archive "$BRANCH" Repo_abpe/abpe_shaduler/incoming Repo_abpe/abpe_ui/incoming | tar -x -C "$TMP"

mkdir -p "$LIVE_APP"
# P = protect: Live-only migrations/0*.py nicht löschen (makemigrations auf Live)
rsync -a --delete \
  --filter='P migrations/0*.py' \
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

# Browser lädt oft STATIC_ROOT — parallel dorthin kopieren (collectstatic optional)
STATICFILES="${STATICFILES:-/opt/abpe/backend/staticfiles}"
if [[ -d "$STATICFILES" ]]; then
  mkdir -p "$STATICFILES/abpe_ui/css/mod" "$STATICFILES/abpe_ui/js/mod"
  cp -a "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css" \
    "$STATICFILES/abpe_ui/css/mod/mod-shaduler.css"
  cp -a "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js" \
    "$STATICFILES/abpe_ui/js/mod/mod-shaduler.js"
  cp -a "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler-kalender.js" \
    "$STATICFILES/abpe_ui/js/mod/mod-shaduler-kalender.js"
  echo "OK — auch nach $STATICFILES/abpe_ui/… kopiert"
fi

for lang in de en; do
  mkdir -p "$LIVE_UI/static/abpe_ui/i18n/$lang/modules/shaduler"
  cp -a "$TMP/Repo_abpe/abpe_ui/incoming/i18n/$lang/modules/shaduler/." \
    "$LIVE_UI/static/abpe_ui/i18n/$lang/modules/shaduler/"
  if [[ -d "$STATICFILES" ]]; then
    mkdir -p "$STATICFILES/abpe_ui/i18n/$lang/modules/shaduler"
    cp -a "$LIVE_UI/static/abpe_ui/i18n/$lang/modules/shaduler/." \
      "$STATICFILES/abpe_ui/i18n/$lang/modules/shaduler/" 2>/dev/null || true
  fi
done

echo "OK — Dateien sync."
echo
echo "Periodik braucht abpe-scheduler-loop (ohne ihn feuert email_index nie):"
echo "  supervisorctl start abpe-scheduler-loop"
echo "  supervisorctl status abpe-django abpe-celery abpe-scheduler-loop"
echo
echo "Scheduler-Jobs neu registrieren (email_index alle 3 Min, since_days=1, incremental):"
echo "  cd /opt/abpe/backend && /opt/abpe/venv311/bin/python manage.py register_scheduler_jobs"
echo "  supervisorctl restart abpe-django abpe-celery"
echo
echo "Optional zusätzlich: collectstatic --noinput"
echo
echo "Diagnose: bash scripts/PROBE-shaduler-inbox-refresh.sh"
