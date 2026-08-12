#!/usr/bin/env bash
# Overnight-Batch: alle neuesten AID-PDFs unter AID_profile/aaa → Pipeline → neu/cv
# Danach Repro-Vergleich Original vs neu/cv → artifacts/aaa-repro (für Git-Sync)
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap
#   git pull origin cursor/cv-extractor-7f07
#   bash scripts/SAFE-cv-extractor-edit.sh deploy
#   bash scripts/aaa-overnight-batch.sh              # Celery async (empfohlen über Nacht)
#   bash scripts/aaa-overnight-batch.sh --dry-run
#   bash scripts/aaa-overnight-batch.sh --sync --limit 3   # Test 3 Profile sync
#   bash scripts/aaa-overnight-batch.sh --force            # auch schon importierte neu
#   bash scripts/aaa-overnight-batch.sh --compare-only     # nur Report
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
LETTER="${LETTER:-aaa}"
BRANCH="${BRANCH:-cursor/cv-extractor-7f07}"
OUT="${OUT:-$REPO/artifacts/${LETTER}-repro}"
LOG="${LOG:-/tmp/${LETTER}-overnight-$(date +%Y%m%d-%H%M%S).log}"

DRY=0
FORCE=0
SYNC=0
COMPARE_ONLY=0
LIMIT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --force) FORCE=1; shift ;;
    --sync) SYNC=1; shift ;;
    --compare-only) COMPARE_ONLY=1; shift ;;
    --limit) LIMIT="${2:-0}"; shift 2 ;;
    --letter) LETTER="${2:-aaa}"; OUT="$REPO/artifacts/${LETTER}-repro"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

exec > >(tee -a "$LOG") 2>&1

echo "======== AAA Overnight Batch ========"
echo "REPO=$REPO BACKEND=$BACKEND LETTER=$LETTER"
echo "OUT=$OUT LOG=$LOG"
echo "DRY=$DRY FORCE=$FORCE SYNC=$SYNC COMPARE_ONLY=$COMPARE_ONLY LIMIT=$LIMIT"
echo "Start: $(date -Iseconds)"
echo

cd "$REPO"
git fetch origin "$BRANCH" || true
git checkout "$BRANCH" || true
git pull origin "$BRANCH" || true

if [[ "$COMPARE_ONLY" -eq 0 ]]; then
  echo ">>> Deploy SAFE files (falls nötig)"
  bash "$REPO/scripts/SAFE-cv-extractor-edit.sh" deploy || {
    echo "WARN: SAFE deploy fehlgeschlagen — fahre mit Live-Code fort"
  }

  cd "$BACKEND"
  # shellcheck disable=SC1091
  [[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
  [[ -f venv311/bin/activate ]] && source venv311/bin/activate

  ARGS=(import_aid_profiles --letter "$LETTER")
  [[ "$DRY" -eq 1 ]] && ARGS+=(--dry-run)
  [[ "$FORCE" -eq 1 ]] && ARGS+=(--no-skip-existing)
  [[ "$SYNC" -eq 1 ]] && ARGS+=(--sync)
  [[ "$LIMIT" -gt 0 ]] && ARGS+=(--limit "$LIMIT")

  echo ">>> python3 manage.py ${ARGS[*]}"
  python3 manage.py "${ARGS[@]}"

  if [[ "$SYNC" -eq 0 && "$DRY" -eq 0 ]]; then
    echo
    echo "Celery läuft async. Warte auf neu/cv …"
    echo "Optional monitoren:"
    echo "  watch -n 30 'find /mnt/public/Berater/AID_profile/$LETTER -path \"*/neu/cv/AID-*.pdf\" | wc -l'"
    echo
    echo "Wenn fertig (oder morgens):"
    echo "  bash $REPO/scripts/aaa-overnight-batch.sh --compare-only"
  fi
fi

if [[ "$DRY" -eq 1 ]]; then
  echo "Dry-run: kein Compare."
  exit 0
fi

# Compare wenn sync-mode, compare-only, oder FORCE nach sync
if [[ "$COMPARE_ONLY" -eq 1 || "$SYNC" -eq 1 ]]; then
  cd "$BACKEND"
  # shellcheck disable=SC1091
  [[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
  [[ -f venv311/bin/activate ]] && source venv311/bin/activate

  mkdir -p "$OUT"
  echo ">>> compare_aid_neu_cv → $OUT"
  python3 manage.py compare_aid_neu_cv --letter "$LETTER" --out "$OUT"

  echo
  echo ">>> Git-Sync der Artifacts (Cloud-Agent kann dann lesen)"
  cd "$REPO"
  git add "artifacts/${LETTER}-repro" || true
  if git diff --cached --quiet; then
    echo "Keine neuen Artifact-Änderungen."
  else
    git commit -m "chore: ${LETTER} repro original vs neu/cv $(date +%Y-%m-%d)" || true
    git push -u origin "$BRANCH" || {
      echo "WARN: git push fehlgeschlagen — bitte manuell pushen"
    }
  fi
fi

echo
echo "Ende: $(date -Iseconds)"
echo "Log: $LOG"
