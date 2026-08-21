#!/usr/bin/env bash
# Retry FAIL-Zeilen aus einem gulp-batch result.tsv (convert / no_neu_cv).
#
# ucs5 — 9 Convert-Fails aus Overnight-Batch:
#   cd /mnt/public/udoo-reprap && git pull origin cursor/gulp-keyword-pipeline-1532
#   FORCE=1 bash scripts/SAFE-gulp-content-deploy.sh deploy   # Import-Fix + Publish
#
#   # optional: Postgres-Idle-Sessions prüfen
#   sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity;"
#
#   RESULT_TSV=/tmp/gulp-batch-20260820-231543/result.tsv \
#   NOTE_FILTER=convert \
#   GULP_TXT_ROOT=/tmp/gulp-batch-20260820-231543/source-txt \
#   VERSION_TAG=1.0.0.5 \
#     bash scripts/RETRY-gulp-batch-fails.sh
#
# 3× no_neu_cv (nach Deploy des Import-Fixes; Convert-PDF oft schon da):
#   RESULT_TSV=/tmp/gulp-batch-20260820-231543/result.tsv \
#   NOTE_FILTER=no_neu_cv \
#   GULP_TXT_ROOT=/tmp/gulp-batch-20260820-231543/source-txt \
#   VERSION_TAG=1.0.0.5 \
#     bash scripts/RETRY-gulp-batch-fails.sh
#
# Nur Diagnose der 3 no_neu_cv (kein Pipeline-Lauf):
#   DIAG=1 NOTE_FILTER=no_neu_cv \
#   RESULT_TSV=/tmp/gulp-batch-20260820-231543/result.tsv \
#     bash scripts/RETRY-gulp-batch-fails.sh
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
AID_ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"
RESULT_TSV="${RESULT_TSV:-}"
NOTE_FILTER="${NOTE_FILTER:-convert}"   # convert | no_neu_cv | all
GULP_TXT_ROOT="${GULP_TXT_ROOT:-}"
VERSION_TAG="${VERSION_TAG:-1.0.0.5}"
EXECUTE="${EXECUTE:-1}"
DIAG="${DIAG:-0}"
OUT_LOG="${OUT_LOG:-/tmp/gulp-retry-$(date +%Y%m%d-%H%M%S)}"

if [[ -z "$RESULT_TSV" || ! -f "$RESULT_TSV" ]]; then
  echo "FAIL: RESULT_TSV setzen (Pfad zu result.tsv)" >&2
  exit 1
fi

mkdir -p "$OUT_LOG"
NEED_OUT="$OUT_LOG/need_retry.tsv"

python3 - "$RESULT_TSV" "$NOTE_FILTER" "$NEED_OUT" <<'PY'
import csv, re, sys
from pathlib import Path

src, note_filter, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
rows = list(csv.DictReader(src.open(), delimiter="\t"))
umlaut = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})

def split_dir(d):
    d = (d or "").strip()
    if "_" not in d:
        return d, ""
    last, first = d.split("_", 1)
    return last.replace("-", " "), first.replace("_", " ").replace("-", " ")

want = []
for r in rows:
    if r.get("status") != "FAIL":
        continue
    note = (r.get("note") or "").strip()
    if note_filter != "all" and note != note_filter:
        continue
    letter = (r.get("letter") or "").strip()
    dname = (r.get("dir") or "").strip()
    if not dname:
        continue
    last, first = split_dir(dname)
    want.append({
        "contact_id": r.get("contact_id") or "",
        "gulp_id": r.get("gulp_id") or "",
        "last": last.title() if last else "",
        "first": first.title() if first else "",
        "letter": letter,
        "dir": dname,
        "note": note,
        "profil_len": "0",
    })

out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", encoding="utf-8") as f:
    f.write("cat\tcontact_id\tgulp_id\tlast\tfirst\tfs_letter\tfs_dir\thas_neu_pdf\tprofil_len\n")
    for w in want:
        f.write(
            f"fs_dir_no_neu\t{w['contact_id']}\t{w['gulp_id']}\t"
            f"{w['last']}\t{w['first']}\t{w['letter']}\t{w['dir']}\t0\t{w['profil_len']}\n"
        )
print(f"retry_rows={len(want)} filter={note_filter} → {out}")
for w in want:
    print(f"  {w['note']:12} {w['letter']}/{w['dir']} cid={w['contact_id']}")
PY

echo "NEED=$NEED_OUT"
echo "OUT_LOG=$OUT_LOG"

if [[ "$DIAG" == "1" ]]; then
  echo
  echo "======== DIAG no_neu_cv / FAIL paths ========"
  while IFS=$'\t' read -r cat cid gid last first letter dname has_neu plen || [[ -n "${cat:-}" ]]; do
    [[ "$cat" == "cat" || -z "$cat" ]] && continue
    echo "── $letter/$dname"
    for L in "$letter" sch sss; do
      [[ -z "$L" ]] && continue
      p="$AID_ROOT/$L/$dname"
      if [[ -d "$p" ]]; then
        echo "  DIR  $p"
        ls -la "$p"/*.pdf 2>/dev/null | head -5 || echo "  (keine PDF im Person-Root)"
        if [[ -d "$p/neu/cv" ]]; then
          echo "  neu/cv:"
          ls -la "$p/neu/cv" | head -8
        else
          echo "  neu/cv: FEHLT"
        fi
      fi
    done
    # Convert-Log aus Original-Batch falls vorhanden
    blog="$(dirname "$RESULT_TSV")/convert-$dname/result.tsv"
    if [[ -f "$blog" ]]; then
      echo "  convert-log: $(tr '\t' ' ' <"$blog" | tail -1)"
    fi
  done <"$NEED_OUT"
  echo "DIAG fertig — kein Pipeline-Lauf."
  exit 0
fi

cd "$REPO"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate

export NEED="$NEED_OUT"
export LIMIT=0
export EXECUTE
export VERSION_TAG
export GULP_TXT_ROOT
export OUT_LOG
export SKIP_EXISTING_NEU=0
export PAUSE_BETWEEN="${PAUSE_BETWEEN:-3}"

bash "$REPO/scripts/BATCH-gulp-to-aid-pipeline.sh"

echo
echo "Retry fertig. Result: $OUT_LOG/result.tsv"
echo "Sync (optional):"
echo "  RESULT_TSV=$OUT_LOG/result.tsv SOURCE_TXT=${GULP_TXT_ROOT:-} \\"
echo "    bash $REPO/scripts/SYNC-gulp-batch-neu-to-repo.sh"
