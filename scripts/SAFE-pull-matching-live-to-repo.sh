#!/usr/bin/env bash
# Live-Ist-Stand → Repo (aktueller Outreach/Matching-Branch).
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/matching-shortlist-weights-1532
#   bash scripts/SAFE-pull-matching-live-to-repo.sh
#
# Optional:
#   NO_BACKUP=1 bash scripts/SAFE-pull-matching-live-to-repo.sh
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/matching-shortlist-weights-1532}"

cd "$REPO"
git fetch origin "$BRANCH"
git checkout "$BRANCH" 2>/dev/null || git checkout -B "$BRANCH" "origin/$BRANCH"
git pull origin "$BRANCH" || true

# Skript aus dem Branch selbst (nach pull aktuell)
if [[ -f "$REPO/scripts/LIVE-FIRST-pull.sh" ]]; then
  bash "$REPO/scripts/LIVE-FIRST-pull.sh"
else
  bash <(git show "origin/$BRANCH:scripts/LIVE-FIRST-pull.sh")
fi

echo
echo "Danach Cloud-Agent / lokal:"
echo "  git fetch origin && git pull origin $BRANCH"
