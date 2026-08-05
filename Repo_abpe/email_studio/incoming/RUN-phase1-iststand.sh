#!/usr/bin/env bash
# Phase 1 — Ist-Stand: Code-Sync ucs5 → Repo + DB-Snapshot → optional git commit/push
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap && git pull
#   bash Repo_abpe/email_studio/incoming/RUN-phase1-iststand.sh
#   bash Repo_abpe/email_studio/incoming/RUN-phase1-iststand.sh --commit --push
#
# Flags:
#   --commit   git add + commit nach Sync/Export
#   --push     git push (impliziert --commit)
#   --no-sync  nur DB-Export (kein RUN-sync-from-ucs5.sh)
#   --no-data  nur Code-Sync (kein dumpdata)

set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DO_SYNC=1
DO_DATA=1
DO_COMMIT=0
DO_PUSH=0

for arg in "$@"; do
  case "$arg" in
    --commit) DO_COMMIT=1 ;;
    --push) DO_COMMIT=1; DO_PUSH=1 ;;
    --no-sync) DO_SYNC=0 ;;
    --no-data) DO_DATA=0 ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *)
      echo "Unbekanntes Flag: $arg" >&2
      exit 1
      ;;
  esac
done

cd "$REPO"

if [[ "$DO_SYNC" -eq 1 ]]; then
  echo "=== 1/2 Code-Sync ==="
  bash "${SCRIPT_DIR}/RUN-sync-from-ucs5.sh"
else
  echo "=== 1/2 Code-Sync übersprungen (--no-sync) ==="
fi

if [[ "$DO_DATA" -eq 1 ]]; then
  echo ""
  echo "=== 2/2 DB-Snapshot ==="
  bash "${SCRIPT_DIR}/export-email-studio-data.sh"
else
  echo ""
  echo "=== 2/2 DB-Snapshot übersprungen (--no-data) ==="
fi

if [[ "$DO_COMMIT" -eq 1 ]]; then
  echo ""
  echo "=== git commit ==="
  git add Repo_abpe/email_studio/ Repo_abpe/abpe_ki_wiz/ 2>/dev/null || git add Repo_abpe/email_studio/
  if git diff --cached --quiet; then
    echo "Keine Änderungen zum Committen."
  else
    git commit -m "chore(email-studio): Phase-1 Ist-Stand (Code-Sync + DB-Snapshot)"
  fi
fi

if [[ "$DO_PUSH" -eq 1 ]]; then
  echo ""
  echo "=== git push ==="
  BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  git push -u origin "$BRANCH"
fi

echo ""
echo "Phase 1 fertig."
echo "Danach: Analyse/Report in Repo_abpe/email_studio/docs/CONSOLIDATION.md"
