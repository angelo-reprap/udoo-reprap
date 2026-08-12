#!/usr/bin/env bash
# Ein Befehl auf ucs5: Live → Git (schnell, leichtes Backup, Commit+Push).
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/matching-ki-anfrage-wizard-7f07
#   bash <(git show origin/cursor/matching-ki-anfrage-wizard-7f07:scripts/LIVE-FIRST-pull.sh)
#
# Backup liegt unter /opt/abpe/backups/matching-live-*/ — nur kritische
# Dateien (views/urls/models + UI-JS), KEIN 1.4G CRM-Tar.
# Notfall-Vollbackup: FULL_BACKUP=1 … LIVE-FIRST-pull.sh
#
set -euo pipefail
REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/matching-ki-anfrage-wizard-7f07}"
EXTRA=()
[[ "${FULL_BACKUP:-0}" == "1" ]] && EXTRA+=(--full-backup)
[[ "${NO_BACKUP:-0}" == "1" ]] && EXTRA+=(--no-backup)

cd "$REPO"
git fetch origin "$BRANCH"
git checkout "$BRANCH" 2>/dev/null || git checkout -B "$BRANCH" "origin/$BRANCH"
git pull origin "$BRANCH" || true

bash <(git show "origin/$BRANCH:scripts/PULL-matching-from-live.sh") --push "${EXTRA[@]}"

echo
echo "======== LIVE-FIRST fertig ========"
echo "Cloud-Agent: git fetch && git pull origin $BRANCH"
