#!/usr/bin/env bash
# Live → Repo: nur cv_extractor (schnell, ohne Sessions/PDFs/node_modules)
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/cv-extractor-7f07
#   bash <(git show origin/cursor/cv-extractor-7f07:scripts/PULL-cv-extractor-from-live.sh) --push
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/cv-extractor-7f07}"
LIVE_CV="${LIVE_CV:-/opt/abpe/backend/apps/cv_extractor}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/abpe/backups}"
DO_PUSH=0
for arg in "$@"; do
  case "$arg" in
    --push|--commit) DO_PUSH=1 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
  esac
done

TS=$(date +%Y%m%d-%H%M%S)
echo "======== PULL cv_extractor Live → Repo $TS ========"

if [[ ! -d "$LIVE_CV" ]]; then
  echo "FAIL: $LIVE_CV fehlt"
  exit 1
fi
if [[ ! -d "$REPO/.git" ]]; then
  echo "FAIL: $REPO ist kein Git-Repo"
  exit 1
fi

cd "$REPO"
git fetch origin 2>/dev/null || true
if ! git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
  if git rev-parse --verify "origin/$BRANCH" >/dev/null 2>&1; then
    git checkout -B "$BRANCH" "origin/$BRANCH"
  elif git rev-parse --verify origin/master >/dev/null 2>&1; then
    git checkout -B "$BRANCH" origin/master
  else
    git checkout -B "$BRANCH"
  fi
else
  git checkout "$BRANCH"
  git pull origin "$BRANCH" 2>/dev/null || true
fi

BAK="$BACKUP_ROOT/cv-extractor-live-$TS"
mkdir -p "$BAK"
for f in models.py views.py urls.py apps.py admin.py; do
  [[ -f "$LIVE_CV/$f" ]] && cp -a "$LIVE_CV/$f" "$BAK/" || true
done
[[ -d "$LIVE_CV/services" ]] && mkdir -p "$BAK/services" && \
  find "$LIVE_CV/services" -maxdepth 1 -name '*.py' -exec cp -a {} "$BAK/services/" \; 2>/dev/null || true
echo "OK Backup: $BAK ($(du -sh "$BAK" | awk '{print $1}'))"

DEST="$REPO/Repo_abpe/cv_extractor/incoming"
mkdir -p "$DEST"

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
rsync -a --no-links "${RSYNC_EXCLUDES[@]}" "$LIVE_CV/" "$DEST/"
rc=$?
set -e
if [[ "$rc" -ne 0 && "$rc" -ne 23 ]]; then
  echo "FEHLER: rsync exit $rc"
  exit "$rc"
fi

echo "OK → $DEST ($(find "$DEST" -type f | wc -l) Dateien)"
echo "=== Top-Level ==="
ls -la "$DEST" | head -40

STAMP="$REPO/Repo_abpe/.live-pull-stamp-cv-extractor"
{
  echo "ts=$TS"
  echo "iso=$(date -Iseconds)"
  echo "host=$(hostname -f 2>/dev/null || hostname)"
  echo "branch=$(git branch --show-current)"
  echo "live=$LIVE_CV"
  echo "files=$(find "$DEST" -type f | wc -l)"
} > "$STAMP"
echo "OK Stamp → $STAMP"

GITIGNORE="$REPO/.gitignore"
touch "$GITIGNORE"
grep -qxF 'Repo_abpe/cv_extractor/incoming/data/' "$GITIGNORE" 2>/dev/null \
  || echo 'Repo_abpe/cv_extractor/incoming/data/' >> "$GITIGNORE"
grep -qxF '_repo_backups/' "$GITIGNORE" 2>/dev/null || echo '_repo_backups/' >> "$GITIGNORE"

echo
git status -sb | head -30

if [[ "$DO_PUSH" -eq 1 ]]; then
  git add Repo_abpe/cv_extractor Repo_abpe/.live-pull-stamp-cv-extractor .gitignore \
    scripts/PULL-cv-extractor-from-live.sh 2>/dev/null || true
  if git diff --cached --quiet; then
    echo "Nichts zu committen."
  else
    git commit -m "pull(live): cv_extractor Stand von ucs5 ($TS)"
    git push -u origin "$(git branch --show-current)"
    echo "OK gepusht → Branch $(git branch --show-current)"
  fi
fi

echo "======== Ende PULL cv_extractor ========"
echo "Cloud-Agent: git fetch && git checkout $BRANCH && git pull"
