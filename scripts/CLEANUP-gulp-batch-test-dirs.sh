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
set -euo pipefail

AID_ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"
RESULT_TSV="${RESULT_TSV:-$(ls -td /tmp/gulp-batch-*/result.tsv 2>/dev/null | head -1 || true)}"
EXECUTE="${EXECUTE:-0}"
DRY_RUN="${DRY_RUN:-1}"
# auch Consultant in DB? default nein — nur FS
CLEAN_DB="${CLEAN_DB:-0}"
BACKEND="${BACKEND:-/opt/abpe/backend}"

if [[ -z "$RESULT_TSV" || ! -f "$RESULT_TSV" ]]; then
  echo "FAIL: RESULT_TSV fehlt" >&2
  exit 1
fi

echo "RESULT_TSV=$RESULT_TSV EXECUTE=$EXECUTE DRY_RUN=$DRY_RUN"
echo

while IFS=$'\t' read -r status _ _ letter dir _ _ _; do
  [[ "$status" == "status" ]] && continue
  [[ "$status" != "OK" && "$status" != "FAIL" ]] && continue
  [[ -z "$letter" || -z "$dir" ]] && continue
  person="$AID_ROOT/$letter/$dir"
  echo "── $letter/$dir"
  if [[ ! -d "$person" ]]; then
    echo "  (fehlt)"
    continue
  fi
  # neu/cv komplett
  if [[ -d "$person/neu" ]]; then
    echo "  rm -rf $person/neu"
    if [[ "$EXECUTE" == "1" && "$DRY_RUN" != "1" ]]; then
      rm -rf "$person/neu"
    fi
  fi
  # nur vom Batch erzeugte Root-AID-PDFs (1.0.0.0), nicht alles blind
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
done <"$RESULT_TSV"

if [[ "$EXECUTE" != "1" || "$DRY_RUN" == "1" ]]; then
  echo
  echo "Dry-run — zum Löschen:"
  echo "  RESULT_TSV=$RESULT_TSV EXECUTE=1 DRY_RUN=0 bash $0"
fi
