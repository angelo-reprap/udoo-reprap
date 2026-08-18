#!/usr/bin/env bash
# Posteingang ES + Radar Anfragen/Berater reparieren (ucs5).
# Erhält Shaduler Art-Defaults (Regeln-Tab) — kein Blind-Overwrite aus alten Branches.
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/posteingang-radar-fix-1532
#   bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/SYNC-posteingang-radar-fix.sh)
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/posteingang-radar-fix-1532}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"
LIVE_NAMAZU_CMD="${LIVE_NAMAZU_CMD:-/opt/abpe/backend/apps/namazu/management/commands}"
LIVE_SH="${LIVE_SH:-/opt/abpe/backend/apps/abpe_shaduler}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
STATICFILES="${STATICFILES:-/opt/abpe/backend/staticfiles}"
TS=$(date +%Y%m%d-%H%M%S)

cd "$REPO"
git fetch origin "$BRANCH"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git archive "origin/$BRANCH" \
  Repo_abpe/namazu/incoming/management/commands/index_emails.py \
  Repo_abpe/abpe_shaduler/incoming \
  Repo_abpe/abpe_scheduler/incoming/management/commands/scheduler_loop.py \
  Repo_abpe/abpe_ui/incoming/mod-shaduler.js \
  Repo_abpe/abpe_ui/incoming/mod-shaduler.css \
  Repo_abpe/abpe_ui/incoming/mod-shaduler-kalender.js \
  deploy/supervisor/abpe-scheduler-loop.conf \
  | tar -x -C "$TMP"

echo "======== SYNC Posteingang+Radar ($BRANCH) $TS ========"

# 1) namazu index_emails — leere SINCE prunt nicht mehr
SRC_IDX="$TMP/Repo_abpe/namazu/incoming/management/commands/index_emails.py"
if [[ ! -f "$SRC_IDX" ]] || ! grep -q 'kein Prune' "$SRC_IDX"; then
  echo "FAIL: index_emails.py ohne Prune-Fix im Branch"
  exit 1
fi
mkdir -p "$LIVE_NAMAZU_CMD"
if [[ -f "$LIVE_NAMAZU_CMD/index_emails.py" ]]; then
  cp -a "$LIVE_NAMAZU_CMD/index_emails.py" "$LIVE_NAMAZU_CMD/index_emails.py.bak-pe-$TS"
fi
cp -a "$SRC_IDX" "$LIVE_NAMAZU_CMD/index_emails.py"
echo "OK — namazu/index_emails.py (kein Prune bei leerer SINCE)"

# 2) Shaduler Backend (ohne --delete, Migrations schützen)
mkdir -p "$LIVE_SH"
rsync -a \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'migrations/0*.py' \
  "$TMP/Repo_abpe/abpe_shaduler/incoming/" \
  "$LIVE_SH/"
echo "OK — abpe_shaduler (tasks, radar_*, register_scheduler_jobs, inbox_service)"

# Guard: Art-Defaults müssen in UI bleiben
JS_SRC="$TMP/Repo_abpe/abpe_ui/incoming/mod-shaduler.js"
if ! grep -q 'TASK_ART_DEFAULTS_BASE' "$JS_SRC"; then
  echo "FAIL: mod-shaduler.js ohne Art-Defaults — Abbruch (Regeln-Tab schützen)"
  exit 2
fi
if ! grep -q 'staleHint\|RADAR_POLL_MS\|startRadarPoll' "$JS_SRC"; then
  echo "FAIL: mod-shaduler.js ohne Soft-Poll/Stale-Hint"
  exit 2
fi

mkdir -p "$LIVE_UI/static/abpe_ui/js/mod" "$LIVE_UI/static/abpe_ui/css/mod"
for f in mod-shaduler.js mod-shaduler-kalender.js; do
  src="$TMP/Repo_abpe/abpe_ui/incoming/$f"
  [[ -f "$src" ]] || continue
  dst="$LIVE_UI/static/abpe_ui/js/mod/$f"
  [[ -f "$dst" ]] && cp -a "$dst" "${dst}.bak-pe-$TS"
  cp -a "$src" "$dst"
  echo "OK — $f"
done
CSS_SRC="$TMP/Repo_abpe/abpe_ui/incoming/mod-shaduler.css"
if [[ -f "$CSS_SRC" ]]; then
  dst="$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css"
  [[ -f "$dst" ]] && cp -a "$dst" "${dst}.bak-pe-$TS"
  cp -a "$CSS_SRC" "$dst"
  echo "OK — mod-shaduler.css"
fi

if [[ -d "$STATICFILES" ]]; then
  mkdir -p "$STATICFILES/abpe_ui/js/mod" "$STATICFILES/abpe_ui/css/mod"
  cp -a "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js" \
    "$STATICFILES/abpe_ui/js/mod/mod-shaduler.js"
  [[ -f "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler-kalender.js" ]] && \
    cp -a "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler-kalender.js" \
      "$STATICFILES/abpe_ui/js/mod/mod-shaduler-kalender.js"
  [[ -f "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css" ]] && \
    cp -a "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css" \
      "$STATICFILES/abpe_ui/css/mod/mod-shaduler.css"
  echo "OK — staticfiles mirror"
fi

find "$LIVE_SH" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

echo
echo "=== Jobs registrieren (email_index + radar_poll alle 3 Min) ==="
cd "$BACKEND"
"$PYBIN" manage.py register_scheduler_jobs

echo
echo "=== Scheduler-Loop dauerhaft RUNNING ==="
bash <(git -C "$REPO" show "origin/$BRANCH:scripts/ENSURE-abpe-scheduler-loop.sh")

echo
echo "=== Catch-up Posteingang (14 Tage, kein Prune) ==="
"$PYBIN" manage.py index_emails --since-days 14 --folders INBOX --no-prune || {
  echo "WARN: index_emails Catch-up fehlgeschlagen — manuell prüfen"
}

echo
echo "=== Catch-up Radar ==="
"$PYBIN" manage.py radar_dedupe_sources --apply 2>/dev/null || true
"$PYBIN" manage.py radar_fix_published_dates --apply 2>/dev/null || true
"$PYBIN" manage.py radar_run_once --pages 2 --days 2 2>/dev/null \
  || "$PYBIN" - <<'PY'
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from apps.abpe_shaduler.services import radar_fetcher
print(radar_fetcher.poll_once(pages=2, today_only=True, recent_days=2))
PY

echo
echo "=== Radar Berater FM Aktuellste (optional, kurz) ==="
"$PYBIN" manage.py radar_berater_fl_available --limit 48 --pages 2 2>/dev/null || true

supervisorctl restart abpe-django abpe-celery 2>/dev/null || true
sleep 2
supervisorctl status abpe-django abpe-celery abpe-scheduler-loop 2>/dev/null || true

echo
echo "Probe:"
echo "  $PYBIN manage.py shaduler_inbox_probe --fetch --limit 5"
echo "Browser: Ctrl+F5 → Posteingang / Radar Anfragen / Radar Berater / Regeln"
echo "Posteingang: neueste Mails sollten < 1 Tag sein; ‚aktualisiert‘ ≠ Indexer — Scheduler-Loop muss RUNNING sein."
