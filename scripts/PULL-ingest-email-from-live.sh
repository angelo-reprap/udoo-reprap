#!/usr/bin/env bash
# Live → Repo: ingest_email-App nach Repo_abpe/ingest_email/incoming/
#
# Auf ucs5 (Share-Repo) ausführen — Cloud Agent hat keinen SSH auf Live.
#
# WICHTIG: zuerst fetch, sonst kennt origin/… das Script noch nicht:
#   cd /mnt/public/udoo-reprap && git fetch origin cursor/abpe-shaduler-scaffold-7f07
#   bash <(git show origin/cursor/abpe-shaduler-scaffold-7f07:scripts/PULL-ingest-email-from-live.sh)
#
# Danach committen/pushen auf dem Branch, damit der Cloud Agent die Quellen hat.
set -euo pipefail

LIVE="${LIVE:-/opt/abpe/backend/apps/ingest_email}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
DEST="$REPO/Repo_abpe/ingest_email/incoming"
BRANCH="${BRANCH:-cursor/abpe-shaduler-scaffold-7f07}"

if [[ ! -d "$LIVE" ]]; then
  echo "FAIL: $LIVE fehlt."
  echo "Prüfe: ls /opt/abpe/backend/apps/ | grep ingest"
  exit 1
fi

if [[ ! -d "$REPO/.git" ]]; then
  echo "FAIL: $REPO ist kein Git-Repo."
  exit 1
fi

mkdir -p "$DEST"
rsync -a --delete \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache/' \
  --exclude '*.egg-info/' \
  "$LIVE/" "$DEST/"

echo "OK → $DEST"
echo "Dateien: $(find "$DEST" -type f ! -path '*/__pycache__/*' | wc -l)"
echo
echo "Nächste Schritte:"
echo "  cd $REPO"
echo "  git fetch origin && git checkout $BRANCH && git pull origin $BRANCH"
echo "  git add Repo_abpe/ingest_email/incoming"
echo "  git status"
echo "  git commit -m 'Import: ingest_email von Live nach Repo'"
echo "  git push -u origin $BRANCH"
echo
echo "Hinweis: SYNC-abpe-shaduler-files.sh überschreibt NUR abpe_shaduler (+ Shaduler-UI),"
echo "         nicht ingest_email. Richtung Sync = Repo → Live."
