#!/usr/bin/env bash
# Ein Befehl auf ucs5: Live → Git (inkl. Commit+Push).
# Danach Cloud-Agent: git pull — erst dann weiterarbeiten / SYNC.
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/matching-ki-anfrage-wizard-7f07
#   bash <(git show origin/cursor/matching-ki-anfrage-wizard-7f07:scripts/LIVE-FIRST-pull.sh)
#
set -euo pipefail
REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/matching-ki-anfrage-wizard-7f07}"

cd "$REPO"
git fetch origin "$BRANCH"
git checkout "$BRANCH" 2>/dev/null || git checkout -B "$BRANCH" "origin/$BRANCH"
git pull origin "$BRANCH" || true

# PULL-Script immer aus dem Branch (frisch), nicht aus alter Working-Copy
bash <(git show "origin/$BRANCH:scripts/PULL-matching-from-live.sh") --push

echo
echo "======== LIVE-FIRST fertig ========"
echo "Cloud-Agent: git fetch && git pull origin $BRANCH"
echo "Dann erst Features / SYNC."
