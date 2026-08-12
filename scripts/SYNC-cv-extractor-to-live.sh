#!/usr/bin/env bash
# Repo → Live: cv_extractor (vorsichtig, ohne data/)
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/cv-extractor-7f07
#   git checkout cursor/cv-extractor-7f07 && git pull
#   bash scripts/SYNC-cv-extractor-to-live.sh
#
# Nur Publish-Dateien (schnell, für neu/cv Test):
#   bash scripts/SYNC-cv-extractor-to-live.sh --publish-only
#
# Danach Django/Celery neu laden, z.B.:
#   systemctl restart abpe-gunicorn abpe-celery  # Namen anpassen
#   # oder touch /opt/abpe/backend/uwsgi.ini / reload
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/cv-extractor-7f07}"
LIVE_CV="${LIVE_CV:-/opt/abpe/backend/apps/cv_extractor}"
SRC="${SRC:-$REPO/Repo_abpe/cv_extractor/incoming}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/abpe/backups}"
STAMP="$REPO/Repo_abpe/.live-pull-stamp-cv-extractor"
PUBLISH_ONLY=0
FORCE=0
DRY=0

for arg in "$@"; do
  case "$arg" in
    --publish-only) PUBLISH_ONLY=1 ;;
    --force) FORCE=1 ;;
    --dry-run) DRY=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
  esac
done

TS=$(date +%Y%m%d-%H%M%S)
echo "======== SYNC cv_extractor Repo → Live $TS ========"

if [[ ! -d "$LIVE_CV" ]]; then
  echo "FAIL: $LIVE_CV fehlt"
  exit 1
fi
if [[ ! -d "$SRC" ]]; then
  echo "FAIL: Repo-Quelle fehlt: $SRC"
  exit 1
fi
if [[ ! -d "$REPO/.git" ]]; then
  echo "FAIL: $REPO ist kein Git-Repo"
  exit 1
fi

cd "$REPO"
git fetch origin 2>/dev/null || true
git checkout "$BRANCH" 2>/dev/null || git checkout -B "$BRANCH" "origin/$BRANCH"
git pull origin "$BRANCH" 2>/dev/null || true

if [[ ! -f "$STAMP" && "$FORCE" -ne 1 ]]; then
  echo "FAIL: kein Live-Pull-Stamp ($STAMP)."
  echo "  Erst PULL-cv-extractor-from-live.sh, oder --force"
  exit 1
fi

BAK="$BACKUP_ROOT/cv-extractor-pre-sync-$TS"
mkdir -p "$BAK"
rsync -a --exclude '__pycache__/' --exclude 'data/' --exclude '*.pyc' \
  "$LIVE_CV/" "$BAK/" 2>/dev/null || true
echo "OK Backup: $BAK ($(du -sh "$BAK" 2>/dev/null | awk '{print $1}'))"

RSYNC_FLAGS=(-a --no-links)
[[ "$DRY" -eq 1 ]] && RSYNC_FLAGS+=(--dry-run -v)

PUBLISH_FILES=(
  services/aid_profile_publish.py
  generator/html/html_generator.py
  generator/word/word_generator.py
  management/commands/import_aid_profiles.py
  management/commands/publish_neu_cv.py
  pipeline.py
)

if [[ "$PUBLISH_ONLY" -eq 1 ]]; then
  echo "Modus: --publish-only (nur neu/cv Publish-Dateien)"
  for rel in "${PUBLISH_FILES[@]}"; do
    src="$SRC/$rel"
    dst="$LIVE_CV/$rel"
    if [[ ! -f "$src" ]]; then
      echo "  SKIP (fehlt im Repo): $rel"
      continue
    fi
    mkdir -p "$(dirname "$dst")"
    if [[ "$DRY" -eq 1 ]]; then
      echo "  DRY $rel → $dst"
    else
      cp -a "$src" "$dst"
      echo "  OK  $rel"
    fi
  done
else
  echo "Modus: voller Code-Sync (ohne data/)"
  RSYNC_EXCLUDES=(
    --exclude '__pycache__/'
    --exclude '*.pyc'
    --exclude 'node_modules/'
    --exclude '.git/'
    --exclude 'data/'
    --exclude '*.pdf'
    --exclude '*.docx'
    --exclude '*.doc'
    --exclude '*.bak'
    --exclude '*.bak-*'
    --exclude '.session*'
    --exclude '*password*'
    --exclude '*secret*'
    --exclude '.bak_*/'
  )
  set +e
  rsync "${RSYNC_FLAGS[@]}" "${RSYNC_EXCLUDES[@]}" "$SRC/" "$LIVE_CV/"
  rc=$?
  set -e
  if [[ "$rc" -ne 0 && "$rc" -ne 23 ]]; then
    echo "FEHLER: rsync exit $rc"
    exit "$rc"
  fi
fi

echo
echo "=== Prüfe --dir auf Live ==="
if grep -q "add_argument('--dir'" "$LIVE_CV/management/commands/import_aid_profiles.py" 2>/dev/null; then
  echo "OK: --dir ist im Live-Command"
else
  echo "WARN: --dir fehlt noch in Live-Command"
fi
if [[ -f "$LIVE_CV/services/aid_profile_publish.py" ]]; then
  echo "OK: aid_profile_publish.py liegt auf Live"
else
  echo "WARN: aid_profile_publish.py fehlt auf Live"
fi

echo
echo "Nächste Schritte auf ucs5:"
echo "  1) App/Celery neu laden (gunicorn/uwsgi + celery worker)"
echo "  2) Test:"
echo "     cd /opt/abpe/backend && source venv311/bin/activate"
echo "     python3 manage.py import_aid_profiles --help   # muss --dir zeigen"
echo "     python3 manage.py import_aid_profiles --letter ttt --dir troschke_thomas --sync --no-skip-existing"
echo "     ls -la /mnt/public/Berater/AID_profile/ttt/troschke_thomas/neu/cv/"
echo "======== Ende SYNC cv_extractor ========"
