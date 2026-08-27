#!/usr/bin/env bash
# Live abpe_edms → Git. Schreibt NICHT nach /opt/abpe (kein Deploy).
#
# ucs5:
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/matching-templates-dms-ee01
#   bash <(git show origin/cursor/matching-templates-dms-ee01:scripts/SAFE-pull-abpe-edms-live-to-repo.sh)
#
# Danach Cloud-Agent:
#   git fetch origin && git pull origin cursor/matching-templates-dms-ee01
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/matching-templates-dms-ee01}"
LIVE_EDMS="${LIVE_EDMS:-/opt/abpe/backend/apps/abpe_edms}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/abpe/backups}"
DO_PUSH=1
for arg in "$@"; do
  case "$arg" in
    --no-push) DO_PUSH=0 ;;
    -h|--help)
      sed -n '2,14p' "$0"
      exit 0
      ;;
  esac
done

TS=$(date +%Y%m%d-%H%M%S)
echo "======== LIVE abpe_edms → Repo $TS ========"
echo "Live bleibt unangetastet. Ziel: $REPO  Branch: $BRANCH"

[[ -d "$REPO/.git" ]] || { echo "FAIL: $REPO ist kein Git-Repo"; exit 1; }
[[ -d "$LIVE_EDMS" ]] || { echo "FAIL: Live-EDMS fehlt: $LIVE_EDMS"; exit 1; }

cd "$REPO"
git fetch origin "$BRANCH"
git checkout "$BRANCH" 2>/dev/null || git checkout -B "$BRANCH" "origin/$BRANCH"
git pull origin "$BRANCH" || true

BAK="$BACKUP_ROOT/abpe-edms-live-copy-$TS"
mkdir -p "$BAK"
for f in urls.py views.py models.py; do
  [[ -f "$LIVE_EDMS/$f" ]] && cp -a "$LIVE_EDMS/$f" "$BAK/$f" || true
done
[[ -d "$LIVE_EDMS/services" ]] && mkdir -p "$BAK/services" && \
  find "$LIVE_EDMS/services" -maxdepth 1 -name '*.py' -exec cp -a {} "$BAK/services/" \; 2>/dev/null || true
echo "OK Kopie (kein Restore nötig, Live unverändert): $BAK"

DEST="$REPO/Repo_abpe/abpe_edms/incoming"
mkdir -p "$DEST"
set +e
rsync -a --no-links \
  --exclude '__pycache__/' --exclude '*.pyc' --exclude '*.pyo' \
  --exclude '*.bak' --exclude '*.bak-*' --exclude '.session*' \
  --exclude '*password*' --exclude '*secret*' \
  --exclude '.git/' --exclude 'node_modules/' \
  --exclude '*.pdf' --exclude '*.docx' --exclude '*.doc' \
  "$LIVE_EDMS/" "$DEST/"
rc=$?
set -e
if [[ "$rc" -ne 0 && "$rc" -ne 23 ]]; then
  echo "FEHLER: rsync exit $rc"
  exit "$rc"
fi
mkdir -p "$DEST/migrations"
touch "$DEST/migrations/__init__.py"
for must in urls.py views.py models.py; do
  [[ -f "$DEST/$must" ]] || { echo "FEHLER: $DEST/$must fehlt nach rsync"; exit 1; }
done
echo "OK → $DEST  (views=$(wc -l < "$DEST/views.py") Z)"

STAMP="$REPO/Repo_abpe/.live-pull-stamp-abpe-edms"
{
  echo "ts=$TS"
  echo "iso=$(date -Iseconds)"
  echo "host=$(hostname -f 2>/dev/null || hostname)"
  echo "branch=$(git -C "$REPO" branch --show-current)"
  echo "mode=live-to-repo-edms-only"
  echo "live_untouched=1"
} > "$STAMP"

echo
git status -sb | head -30
git diff --stat -- Repo_abpe/abpe_edms | tail -20 || true

if [[ "$DO_PUSH" -eq 1 ]]; then
  git add Repo_abpe/abpe_edms Repo_abpe/.live-pull-stamp-abpe-edms
  if git diff --cached --quiet; then
    echo "Nichts zu committen — Repo-EDMS entspricht bereits Live."
  else
    git commit -m "pull(live): abpe_edms Ist-Stand von ucs5 ($TS)"
    git push -u origin "$(git branch --show-current)"
    echo "OK gepusht"
  fi
else
  echo "Ohne Commit (--no-push). Danach: git add Repo_abpe/abpe_edms && git commit && git push"
fi

echo
echo "======== fertig — Live-Server unverändert ========"
echo "Cloud-Agent: git fetch origin && git pull origin $BRANCH"
