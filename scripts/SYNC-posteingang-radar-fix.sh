#!/usr/bin/env bash
# SICHERER Deploy Posteingang/Radar — KEIN Blind-rsync mehr auf ganz abpe_shaduler.
#
# Pflicht vorher (ucs5):
#   1) Inventar Live
#   2) Archiv backup_restore -save für jede Datei
#   3) Nur Allowlist kopieren
#
#   ALLOW_LIVE_WRITE=1 bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/SYNC-posteingang-radar-fix.sh)
#
# Ohne ALLOW_LIVE_WRITE=1: nur Dry-Run / Diff — schreibt NICHTS.
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
ALLOW_LIVE_WRITE="${ALLOW_LIVE_WRITE:-0}"
SKIP_ARCHIVE="${SKIP_ARCHIVE:-0}"
TS=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="/opt/abpe/backups/pe-radar-pre-$TS"

# Nur diese Relativpfade unter Live (explizit — kein Tree-rsync)
ALLOWLIST=(
  "apps/namazu/management/commands/index_emails.py"
  "apps/abpe_shaduler/tasks.py"
  "apps/abpe_shaduler/management/commands/register_scheduler_jobs.py"
  "apps/abpe_shaduler/services/inbox_service.py"
  "apps/abpe_shaduler/services/radar_fetcher.py"
  "apps/abpe_shaduler/services/radar_grouper.py"
  "apps/abpe_shaduler/services/radar_berater_fl.py"
  "apps/abpe_shaduler/services/radar_berater_service.py"
  "apps/abpe_shaduler/services/radar_berater_gulp.py"
  "apps/abpe_shaduler/services/radar_berater_index.py"
  "apps/abpe_ui/static/abpe_ui/js/mod/mod-shaduler.js"
  "apps/abpe_ui/static/abpe_ui/css/mod/mod-shaduler.css"
)

REPO_MAP=(
  "Repo_abpe/namazu/incoming/management/commands/index_emails.py|apps/namazu/management/commands/index_emails.py"
  "Repo_abpe/abpe_shaduler/incoming/tasks.py|apps/abpe_shaduler/tasks.py"
  "Repo_abpe/abpe_shaduler/incoming/management/commands/register_scheduler_jobs.py|apps/abpe_shaduler/management/commands/register_scheduler_jobs.py"
  "Repo_abpe/abpe_shaduler/incoming/services/inbox_service.py|apps/abpe_shaduler/services/inbox_service.py"
  "Repo_abpe/abpe_shaduler/incoming/services/radar_fetcher.py|apps/abpe_shaduler/services/radar_fetcher.py"
  "Repo_abpe/abpe_shaduler/incoming/services/radar_grouper.py|apps/abpe_shaduler/services/radar_grouper.py"
  "Repo_abpe/abpe_shaduler/incoming/services/radar_berater_fl.py|apps/abpe_shaduler/services/radar_berater_fl.py"
  "Repo_abpe/abpe_shaduler/incoming/services/radar_berater_service.py|apps/abpe_shaduler/services/radar_berater_service.py"
  "Repo_abpe/abpe_shaduler/incoming/services/radar_berater_gulp.py|apps/abpe_shaduler/services/radar_berater_gulp.py"
  "Repo_abpe/abpe_shaduler/incoming/services/radar_berater_index.py|apps/abpe_shaduler/services/radar_berater_index.py"
  "Repo_abpe/abpe_ui/incoming/mod-shaduler.js|apps/abpe_ui/static/abpe_ui/js/mod/mod-shaduler.js"
  "Repo_abpe/abpe_ui/incoming/mod-shaduler.css|apps/abpe_ui/static/abpe_ui/css/mod/mod-shaduler.css"
)

cd "$REPO"
git fetch origin "$BRANCH"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
PATHS=()
for pair in "${REPO_MAP[@]}"; do
  PATHS+=("${pair%%|*}")
done
git archive "origin/$BRANCH" "${PATHS[@]}" | tar -x -C "$TMP"

echo "======== SYNC Posteingang+Radar SAFE ($BRANCH) $TS ========"
echo "ALLOW_LIVE_WRITE=$ALLOW_LIVE_WRITE  SKIP_ARCHIVE=$SKIP_ARCHIVE"
echo

echo "=== Live vs Repo (sha) ==="
differs=0
for pair in "${REPO_MAP[@]}"; do
  rel="${pair%%|*}"
  live_rel="${pair##*|}"
  src="$TMP/$rel"
  dst="$BACKEND/$live_rel"
  if [[ ! -f "$src" ]]; then
    echo "MISS repo $rel"
    continue
  fi
  if [[ ! -f "$dst" ]]; then
    echo "NEW  live fehlt: $dst"
    differs=1
    continue
  fi
  hs=$(sha256sum "$src" | awk '{print $1}')
  hd=$(sha256sum "$dst" | awk '{print $1}')
  if [[ "$hs" == "$hd" ]]; then
    echo "SAME $live_rel"
  else
    echo "DIFF $live_rel"
    echo "     live mtime=$(stat -c '%y' "$dst" 2>/dev/null || true)"
    differs=1
  fi
done
echo

if [[ "$ALLOW_LIVE_WRITE" != "1" ]]; then
  echo "DRY-RUN — nichts geschrieben."
  echo "Wenn Diff ok und Archiv gemacht:"
  echo "  ALLOW_LIVE_WRITE=1 bash <(git show origin/$BRANCH:scripts/SYNC-posteingang-radar-fix.sh)"
  exit 0
fi

mkdir -p "$BACKUP_DIR"
echo "=== Snapshot → $BACKUP_DIR ==="
for pair in "${REPO_MAP[@]}"; do
  live_rel="${pair##*|}"
  dst="$BACKEND/$live_rel"
  [[ -f "$dst" ]] || continue
  mkdir -p "$BACKUP_DIR/$(dirname "$live_rel")"
  cp -a "$dst" "$BACKUP_DIR/$live_rel"
done
echo "OK tree snapshot"

if [[ "$SKIP_ARCHIVE" != "1" && -f "$BACKEND/apps/abpe_ui/backup_restore.py" ]]; then
  echo "=== backup_restore -save ==="
  cd "$BACKEND"
  for pair in "${REPO_MAP[@]}"; do
    live_rel="${pair##*|}"
    dst="$BACKEND/$live_rel"
    [[ -f "$dst" ]] || continue
    "$PYBIN" apps/abpe_ui/backup_restore.py -save "$live_rel" \
      -m "vor pe-radar SYNC $TS" 2>/dev/null \
      || echo "WARN archive skip $live_rel"
  done
fi

echo "=== Copy Allowlist ==="
for pair in "${REPO_MAP[@]}"; do
  rel="${pair%%|*}"
  live_rel="${pair##*|}"
  src="$TMP/$rel"
  dst="$BACKEND/$live_rel"
  [[ -f "$src" ]] || continue
  mkdir -p "$(dirname "$dst")"
  cp -a "$dst" "${dst}.bak-pe-$TS" 2>/dev/null || true
  cp -a "$src" "$dst"
  echo "OK $live_rel"
done

if [[ -d "$STATICFILES" ]]; then
  mkdir -p "$STATICFILES/abpe_ui/js/mod" "$STATICFILES/abpe_ui/css/mod"
  cp -a "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js" \
    "$STATICFILES/abpe_ui/js/mod/mod-shaduler.js" 2>/dev/null || true
  cp -a "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css" \
    "$STATICFILES/abpe_ui/css/mod/mod-shaduler.css" 2>/dev/null || true
fi

echo
echo "Fertig. KEIN Tree-rsync. Snapshot: $BACKUP_DIR"
echo "Jobs nur wenn Scheduler-API erreichbar (nicht localhost:8000 blind):"
echo "  cd $BACKEND && $PYBIN manage.py register_scheduler_jobs"
echo "Loop: bash <(git show origin/$BRANCH:scripts/ENSURE-abpe-scheduler-loop.sh)"
echo "Catch-up Indexer bewusst SEPARAT (lang):"
echo "  $PYBIN manage.py index_emails --since-days 14 --folders INBOX --no-prune"
