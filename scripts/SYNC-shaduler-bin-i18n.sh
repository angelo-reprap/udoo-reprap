#!/usr/bin/env bash
# Nur Shaduler-i18n-bin nach Live deployen (kein Full-SYNC).
#
#   cd /mnt/public/udoo-reprap
#   bash <(git show origin/cursor/shaduler-all-in-one-7f07:scripts/SYNC-shaduler-bin-i18n.sh)
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-origin/cursor/shaduler-all-in-one-7f07}"
LIVE_BIN="${LIVE_BIN:-/opt/abpe/backend/apps/abpe_shaduler/bin}"

cd "$REPO"
git fetch origin cursor/shaduler-all-in-one-7f07 || true

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

git archive "$BRANCH" Repo_abpe/abpe_shaduler/incoming/bin | tar -x -C "$TMP"

mkdir -p "$LIVE_BIN"
rsync -a --delete \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "$TMP/Repo_abpe/abpe_shaduler/incoming/bin/" \
  "$LIVE_BIN/"

echo "OK — $LIVE_BIN"
ls -la "$LIVE_BIN"
echo
echo "Test:"
echo "  cd /opt/abpe/backend && python3 apps/abpe_shaduler/bin/i18n_translator.py --check"
