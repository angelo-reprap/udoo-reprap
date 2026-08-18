#!/usr/bin/env bash
# ucs5 → Git: Letter-Batch-Artefakte committen, damit Cloud-Agent lesen kann.
#
#   bash scripts/sync-letter-artifacts.sh bbb
#   bash scripts/sync-letter-artifacts.sh bbb artifacts/aid-bbb-20260817-101535
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
LETTER="${1:-bbb}"
SRC="${2:-}"
BRANCH="${BRANCH:-cursor/cv-extractor-7f07}"

cd "$REPO"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --rebase origin "$BRANCH" || true

if [[ -z "$SRC" ]]; then
  SRC="$(ls -dt "$REPO"/artifacts/aid-"${LETTER}"-* 2>/dev/null | head -1 || true)"
fi
if [[ -z "$SRC" || ! -d "$SRC" ]]; then
  echo "ERROR: kein artifacts/aid-${LETTER}-* gefunden" >&2
  exit 1
fi

rel="${SRC#"$REPO"/}"
echo "Sync: $rel"
git add "$rel"
if git diff --cached --quiet; then
  echo "Nichts Neues zu committen."
  exit 0
fi
git commit -m "chore: ${LETTER} batch repro $(basename "$SRC")"
if git push -u origin "$BRANCH"; then
  echo "OK gepusht → Cloud kann pullen"
else
  echo "WARN: git push fehlgeschlagen (Auth?). Commit lokal vorhanden:" >&2
  echo "  git log -1 --oneline" >&2
  exit 1
fi
