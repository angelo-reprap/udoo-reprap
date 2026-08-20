#!/usr/bin/env bash
# Löscht die 10 Test-Verzeichnisse (Person-Root AID-PDF + neu/cv) nach Review,
# damit der Batch erneut sauber laufen kann.
#
# DRY zuerst:
#   RESULT_TSV=/tmp/gulp-batch-20260820-172849/result.tsv \
#     DRY_RUN=1 bash scripts/CLEANUP-gulp-batch-test-dirs.sh
#
# Wirklich löschen:
#   RESULT_TSV=/tmp/gulp-batch-20260820-172849/result.tsv \
#     EXECUTE=1 bash scripts/CLEANUP-gulp-batch-test-dirs.sh
#
# Zusätzlich kaputte Pfade aus dem 1. Lauf (z.B. wolfsegger_bernd/0):
#   EXTRA_DIRS="wolfsegger_bernd/0" EXECUTE=1 bash scripts/CLEANUP-gulp-batch-test-dirs.sh
#
# Danach Re-Run (nach git pull des Cleaner-Fixes):
#   cd /mnt/public/udoo-reprap && git pull origin cursor/gulp-keyword-pipeline-1532
#   LIMIT=10 bash scripts/BATCH-gulp-to-aid-pipeline.sh
#
set -euo pipefail

AID_ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"
RESULT_TSV="${RESULT_TSV:-$(ls -td /tmp/gulp-batch-*/result.tsv 2>/dev/null | head -1 || true)}"
EXECUTE="${EXECUTE:-0}"
DRY_RUN="${DRY_RUN:-1}"
# auch Consultant in DB? default nein — nur FS
CLEAN_DB="${CLEAN_DB:-0}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
# Zusatzpfade letter/dir (z.B. wolfsegger_bernd/0 aus kaputtem 1. Lauf)
EXTRA_DIRS="${EXTRA_DIRS:-}"

if [[ -z "$RESULT_TSV" || ! -f "$RESULT_TSV" ]]; then
  echo "FAIL: RESULT_TSV fehlt" >&2
  exit 1
fi

echo "RESULT_TSV=$RESULT_TSV EXECUTE=$EXECUTE DRY_RUN=$DRY_RUN"
echo

cleanup_person() {
  local letter="$1" dir="$2"
  local person="$AID_ROOT/$letter/$dir"
  echo "── $letter/$dir"
  if [[ ! -d "$person" ]]; then
    echo "  (fehlt)"
    return 0
  fi
  if [[ -d "$person/neu" ]]; then
    echo "  rm -rf $person/neu"
    if [[ "$EXECUTE" == "1" && "$DRY_RUN" != "1" ]]; then
      rm -rf "$person/neu"
    fi
  fi
  while IFS= read -r -d '' f; do
    echo "  rm $(basename "$f")"
    if [[ "$EXECUTE" == "1" && "$DRY_RUN" != "1" ]]; then
      rm -f "$f"
    fi
  done < <(find "$person" -maxdepth 1 -type f -iname 'AID-*_1.0.0.0.pdf' -print0 2>/dev/null)

  if [[ "$CLEAN_DB" == "1" ]]; then
    echo "  DB cleanup consultant_dir=$dir (via cleanup_aid_test_imports falls vorhanden)"
    if [[ "$EXECUTE" == "1" && "$DRY_RUN" != "1" ]]; then
      cd "$BACKEND"
      # shellcheck disable=SC1091
      [[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
      python3 manage.py cleanup_aid_test_imports --dir "$dir" --yes 2>/dev/null || \
        echo "  WARN: cleanup_aid_test_imports fehlgeschlagen/fehlt"
    fi
  fi
  # leeren Fake-Ordner (dir=0) ganz entfernen
  if [[ "$dir" =~ ^[0-9]+$ ]] && [[ "$EXECUTE" == "1" && "$DRY_RUN" != "1" ]]; then
    if [[ -d "$person" ]] && [[ -z "$(find "$person" -mindepth 1 -maxdepth 1 2>/dev/null | head -1)" ]]; then
      echo "  rmdir empty $person"
      rmdir "$person" 2>/dev/null || true
    fi
  fi
}

while IFS=$'\t' read -r status _ _ letter dir _ _ _; do
  [[ "$status" == "status" ]] && continue
  [[ "$status" != "OK" && "$status" != "FAIL" ]] && continue
  [[ -z "$letter" || -z "$dir" ]] && continue
  cleanup_person "$letter" "$dir"
done <"$RESULT_TSV"

# EXTRA_DIRS="letter/dir letter2/dir2"
for pair in $EXTRA_DIRS; do
  [[ -z "$pair" ]] && continue
  cleanup_person "${pair%%/*}" "${pair#*/}"
done

if [[ "$EXECUTE" != "1" || "$DRY_RUN" == "1" ]]; then
  echo
  echo "Dry-run — zum Löschen:"
  echo "  RESULT_TSV=$RESULT_TSV EXECUTE=1 DRY_RUN=0 bash $0"
fi
