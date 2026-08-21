#!/usr/bin/env bash
# Retry FAIL-Zeilen aus einem gulp-batch result.tsv (convert / no_neu_cv).
#
# WICHTIG: Default DETACH=1 (überlebt SSH/PuTTY-Abbruch).
#
# ucs5 — Convert-Fails erneut (detached):
#   cd /mnt/public/udoo-reprap && git pull origin cursor/gulp-keyword-pipeline-1532
#   FORCE=1 bash scripts/SAFE-gulp-content-deploy.sh deploy
#
#   RESULT_TSV=/tmp/gulp-batch-20260820-231543/result.tsv \
#   NOTE_FILTER=convert \
#   GULP_TXT_ROOT=/tmp/gulp-batch-20260820-231543/source-txt \
#   VERSION_TAG=1.0.0.5 \
#     bash scripts/RETRY-gulp-batch-fails.sh
#
# Resume nach Abbruch (bereits OK / neu/cv werden übersprungen):
#   SKIP_DONE=1  (Default)
#   PREV_RESULT=/tmp/gulp-retry-…/result.tsv   # optional, zusätzlich
#
# Status / Follow:
#   bash scripts/BATCH-gulp-to-aid-detach.sh --status
#   tail -f /tmp/gulp-aid-batch-latest.log
#
# Vordergrund (nur kurze Tests): DETACH=0 …
#
# Diagnose:
#   DIAG=1 NOTE_FILTER=no_neu_cv RESULT_TSV=… bash scripts/RETRY-gulp-batch-fails.sh
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
DETACH="${DETACH:-1}"
SKIP_DONE="${SKIP_DONE:-1}"
PREV_RESULT="${PREV_RESULT:-}"
OUT_LOG="${OUT_LOG:-/tmp/gulp-retry-$(date +%Y%m%d-%H%M%S)}"

if [[ -z "$RESULT_TSV" || ! -f "$RESULT_TSV" ]]; then
  echo "FAIL: RESULT_TSV setzen (Pfad zu result.tsv)" >&2
  exit 1
fi

mkdir -p "$OUT_LOG"
NEED_OUT="$OUT_LOG/need_retry.tsv"

# Neueste Retry-Results unter /tmp automatisch als PREV nutzen
if [[ -z "$PREV_RESULT" ]]; then
  PREV_RESULT="$(ls -t /tmp/gulp-retry-*/result.tsv 2>/dev/null | head -1 || true)"
fi

python3 - "$RESULT_TSV" "$NOTE_FILTER" "$NEED_OUT" "$AID_ROOT" "$SKIP_DONE" "${PREV_RESULT:-}" "${GULP_TXT_ROOT:-}" <<'PY'
import csv, sys
from pathlib import Path

src = Path(sys.argv[1])
note_filter = sys.argv[2]
out = Path(sys.argv[3])
aid_root = Path(sys.argv[4])
skip_done = sys.argv[5] in ("1", "true", "TRUE", "yes")
prev = Path(sys.argv[6]) if sys.argv[6] else None
txt_root = Path(sys.argv[7]) if sys.argv[7] else None

done_dirs = set()
if prev and prev.is_file():
    for r in csv.DictReader(prev.open(), delimiter="\t"):
        if r.get("status") == "OK" and r.get("dir"):
            done_dirs.add(r["dir"].strip())

def has_neu(letter: str, dname: str) -> bool:
    letters = [letter] if letter else []
    for L in ("sch", "sss"):
        if L not in letters:
            letters.append(L)
    for L in letters:
        if not L:
            continue
        neu = aid_root / L / dname / "neu" / "cv"
        try:
            if neu.is_dir() and any(neu.glob("AID-*.pdf")):
                return True
        except OSError:
            continue
    return False

def profil_len(letter: str, dname: str) -> int:
    if not txt_root or not txt_root.is_dir():
        return 0
    cands = []
    if letter:
        cands.append(txt_root / "by-person" / letter / dname / "gulp_profil_c.txt")
        cands.append(txt_root / "txt" / f"{letter}__{dname}.txt")
    bp = txt_root / "by-person"
    if bp.is_dir():
        for sub in bp.iterdir():
            if sub.is_dir():
                cands.append(sub / dname / "gulp_profil_c.txt")
    for p in cands:
        try:
            if p.is_file():
                return p.stat().st_size
        except OSError:
            continue
    return 0

def split_dir(d):
    d = (d or "").strip()
    if "_" not in d:
        return d, ""
    last, first = d.split("_", 1)
    return last.replace("-", " "), first.replace("_", " ").replace("-", " ")

want, skipped = [], []
for r in csv.DictReader(src.open(), delimiter="\t"):
    if r.get("status") != "FAIL":
        continue
    note = (r.get("note") or "").strip()
    if note_filter != "all" and note != note_filter:
        continue
    letter = (r.get("letter") or "").strip()
    dname = (r.get("dir") or "").strip()
    if not dname:
        continue
    if skip_done and (dname in done_dirs or has_neu(letter, dname)):
        skipped.append(f"{letter}/{dname}")
        continue
    last, first = split_dir(dname)
    plen = profil_len(letter, dname)
    want.append({
        "contact_id": r.get("contact_id") or "",
        "gulp_id": r.get("gulp_id") or "",
        "last": last.title() if last else "",
        "first": first.title() if first else "",
        "letter": letter,
        "dir": dname,
        "note": note,
        "profil_len": str(plen),
    })

out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", encoding="utf-8") as f:
    f.write("cat\tcontact_id\tgulp_id\tlast\tfirst\tfs_letter\tfs_dir\thas_neu_pdf\tprofil_len\n")
    for w in want:
        f.write(
            f"fs_dir_no_neu\t{w['contact_id']}\t{w['gulp_id']}\t"
            f"{w['last']}\t{w['first']}\t{w['letter']}\t{w['dir']}\t0\t{w['profil_len']}\n"
        )
print(f"retry_rows={len(want)} skipped_done={len(skipped)} filter={note_filter}")
if prev:
    print(f"prev_result={prev}")
for s in skipped:
    print(f"  SKIP done {s}")
for w in want:
    print(f"  {w['note']:12} {w['letter']}/{w['dir']} cid={w['contact_id']} len={w['profil_len']}")
PY

echo "NEED=$NEED_OUT"
echo "OUT_LOG=$OUT_LOG"
echo "DETACH=$DETACH SKIP_DONE=$SKIP_DONE"

n_need="$(tail -n +2 "$NEED_OUT" | grep -c . || true)"
if [[ "${n_need:-0}" -eq 0 ]]; then
  echo "Nichts zu tun (alles schon OK / neu/cv vorhanden)."
  exit 0
fi

if [[ "$DIAG" == "1" ]]; then
  echo
  echo "======== DIAG FAIL paths ========"
  while IFS=$'\t' read -r cat cid gid last first letter dname has_neu plen || [[ -n "${cat:-}" ]]; do
    [[ "$cat" == "cat" || -z "$cat" ]] && continue
    echo "── $letter/$dname (profil_len=$plen)"
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
export SKIP_EXISTING_NEU=1
export PAUSE_BETWEEN="${PAUSE_BETWEEN:-3}"
export MEM_THRESH="${MEM_THRESH:-82}"
export CPU_THRESH="${CPU_THRESH:-85}"
export THROTTLE_SLEEP="${THROTTLE_SLEEP:-45}"

if [[ "$DETACH" == "1" ]]; then
  echo "Starte detached (überlebt SSH-Disconnect)…"
  bash "$REPO/scripts/BATCH-gulp-to-aid-detach.sh"
  echo
  echo "Follow:  tail -f /tmp/gulp-aid-batch-latest.log"
  echo "Status:  bash $REPO/scripts/BATCH-gulp-to-aid-detach.sh --status"
  echo "Result:  $OUT_LOG/result.tsv  (wächst während des Laufs)"
else
  bash "$REPO/scripts/BATCH-gulp-to-aid-pipeline.sh"
  echo
  echo "Retry fertig. Result: $OUT_LOG/result.tsv"
fi

echo "Sync (nach Fertig):"
echo "  RESULT_TSV=$OUT_LOG/result.tsv SOURCE_TXT=${GULP_TXT_ROOT:-} \\"
echo "    bash $REPO/scripts/SYNC-gulp-batch-neu-to-repo.sh"
