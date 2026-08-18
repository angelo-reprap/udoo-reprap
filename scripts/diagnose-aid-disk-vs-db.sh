#!/usr/bin/env bash
# Disk neu/cv vs ABpE-DB: warum viele PDFs ohne Consultant?
#
# Auf ucs5 (Convert darf parallel laufen):
#   cd /mnt/public/udoo-reprap
#   LETTERS=aaa-zzz bash scripts/diagnose-aid-disk-vs-db.sh
#   LETTERS=ccc-zzz bash scripts/diagnose-aid-disk-vs-db.sh
#
# Outputs unter artifacts/aid-disk-vs-db-<ts>/ :
#   has-neu-cv.tsv          letter/dir/aid/pdf
#   disk-not-in-db.tsv      neu/cv vorhanden, kein Consultant (dir noch AID)
#   db-not-on-disk.tsv      Consultant mit AID, kein neu/cv PDF
#   partial-neu-no-pdf.tsv  html/docx ohne PDF (Rework-Kandidaten)
#   summary.txt
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
OUT="${OUT:-$REPO/artifacts/aid-disk-vs-db-$(date +%Y%m%d-%H%M%S)}"
LETTERS="${LETTERS:-aaa-zzz}"

mkdir -p "$OUT"
exec > >(tee -a "$OUT/run.log") 2>&1

echo "======== AID Disk vs DB ========"
echo "Start: $(date -Iseconds) OUT=$OUT"
echo "LETTERS=$LETTERS ROOT=$ROOT"
echo

_expand_letters() {
  local spec="$1"
  if [[ "$spec" == "ccc-zzz" ]]; then
    python3 -c "print(' '.join(c*3 for c in 'cdefghijklmnopqrstuvwxyz'))"
    return
  fi
  if [[ "$spec" == "aaa-zzz" ]]; then
    python3 -c "print(' '.join(c*3 for c in 'abcdefghijklmnopqrstuvwxyz'))"
    return
  fi
  echo "$spec" | tr ',;' ' '
}

NEU_TSV="$OUT/has-neu-cv.tsv"
PARTIAL="$OUT/partial-neu-no-pdf.tsv"
: > "$NEU_TSV"
: > "$PARTIAL"
echo -e "letter\tdir\taid\tpdf" > "$NEU_TSV"
echo -e "letter\tdir\thtml\tdocx\tpdf\tdetail" > "$PARTIAL"

neu_n=0
partial_n=0
orig_n=0

echo "=== Filesystem Scan ==="
for letter in $(_expand_letters "$LETTERS"); do
  letter_dir="$ROOT/$letter"
  [[ -d "$letter_dir" ]] || continue
  for person_dir in "$letter_dir"/*; do
    [[ -d "$person_dir" ]] || continue
    dir="$(basename "$person_dir")"
    case "$dir" in neu|audit|ada|Neuer\ Ordner*) continue ;; esac

    orig="$(
      find "$person_dir" -maxdepth 1 -type f -iname 'AID-*.pdf' \
        ! -iname '*engl*' ! -iname '*_en.*' ! -iname '*-en.*' \
        ! -iname '*_alt*' ! -iname '*löschen*' ! -iname '*loeschen*' \
        -print -quit 2>/dev/null || true
    )"
    [[ -n "$orig" && -f "$orig" ]] && orig_n=$((orig_n + 1))

    neu_dir="$person_dir/neu/cv"
    [[ -d "$neu_dir" ]] || continue

    pdf="$(
      find "$neu_dir" -maxdepth 1 -type f -iname 'AID-*.pdf' \
        ! -iname '*engl*' ! -iname '*_en.*' ! -iname '*-en.*' \
        -printf '%T@\t%p\n' 2>/dev/null \
      | sort -nr | head -1 | cut -f2- || true
    )"
    html_n="$(find "$neu_dir" -maxdepth 1 -type f \( -iname 'AID-*.html' -o -iname 'AID-*-short.html' \) 2>/dev/null | wc -l | tr -d ' ')"
    docx_n="$(find "$neu_dir" -maxdepth 1 -type f -iname 'AID-*.docx' 2>/dev/null | wc -l | tr -d ' ')"
    pdf_n="$(find "$neu_dir" -maxdepth 1 -type f -iname 'AID-*.pdf' 2>/dev/null | wc -l | tr -d ' ')"

    if [[ -n "$pdf" && -f "$pdf" ]]; then
      base="$(basename "$pdf")"
      aid="${base%.pdf}"
      # short/en variants: keep stem before first extra suffix if needed
      printf '%s\t%s\t%s\t%s\n' "$letter" "$dir" "$aid" "$pdf" >> "$NEU_TSV"
      neu_n=$((neu_n + 1))
    elif [[ "$html_n" -gt 0 || "$docx_n" -gt 0 ]]; then
      printf '%s\t%s\t%s\t%s\t%s\thtml=%s;docx=%s;pdf=%s\n' \
        "$letter" "$dir" "$html_n" "$docx_n" "$pdf_n" \
        "$html_n" "$docx_n" "$pdf_n" >> "$PARTIAL"
      partial_n=$((partial_n + 1))
    fi
  done
done

echo "Original-PDF dirs (Stich): $orig_n"
echo "neu/cv mit PDF:            $neu_n"
echo "partial (html/docx o. PDF):$partial_n"
echo

echo "=== DB Match ==="
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"
export PYTHONPATH="${PYTHONPATH:-$BACKEND}"

python3 - <<PY
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()

from pathlib import Path
from apps.cv_extractor.models import Consultant, ConsultantSkill

out = Path("$OUT")
neu_tsv = out / "has-neu-cv.tsv"
partial = out / "partial-neu-no-pdf.tsv"

# Load disk rows
disk_rows = []
for i, line in enumerate(neu_tsv.read_text(encoding="utf-8").splitlines()):
    if i == 0 or not line.strip():
        continue
    parts = line.split("\t")
    if len(parts) < 4:
        continue
    letter, d, aid, pdf = parts[0], parts[1], parts[2], parts[3]
    disk_rows.append((letter, d, aid, pdf))

dirs_on_disk = {r[1] for r in disk_rows}
aids_on_disk = {r[2] for r in disk_rows}

# All consultants with AID
cons = list(
    Consultant.objects.exclude(aid__isnull=True).exclude(aid="")
    .values_list("id", "aid", "consultant_dir", "first_name", "last_name", "status")
)
by_dir = {}
by_aid = {}
for c in cons:
    cid, aid, cdir, fn, ln, st = c
    if cdir:
        by_dir.setdefault(cdir, []).append(c)
    by_aid[aid] = c

# Skills coverage
sk_dirs = set(
    ConsultantSkill.objects.values_list("consultant__consultant_dir", flat=True).distinct()
)

disk_not_db = out / "disk-not-in-db.tsv"
db_not_disk = out / "db-not-on-disk.tsv"
matched = out / "matched.tsv"
with disk_not_db.open("w", encoding="utf-8") as f_miss, \
     matched.open("w", encoding="utf-8") as f_ok:
    f_miss.write("letter\tdir\taid\treason\tpdf\n")
    f_ok.write("letter\tdir\taid\tmatch\tconsultant_id\tdb_aid\thas_skills\n")
    n_miss = n_ok = 0
    for letter, d, aid, pdf in disk_rows:
        hit = None
        how = ""
        if aid in by_aid:
            hit = by_aid[aid]
            how = "aid"
        elif d in by_dir:
            hit = by_dir[d][0]
            how = "dir"
        if hit is None:
            f_miss.write(f"{letter}\t{d}\t{aid}\tno_consultant\t{pdf}\n")
            n_miss += 1
        else:
            cid, db_aid, *_ = hit
            has_sk = "1" if d in sk_dirs else "0"
            f_ok.write(f"{letter}\t{d}\t{aid}\t{how}\t{cid}\t{db_aid}\t{has_sk}\n")
            n_ok += 1

with db_not_disk.open("w", encoding="utf-8") as f:
    f.write("consultant_id\taid\tconsultant_dir\tname\tstatus\n")
    n_db_miss = 0
    for c in cons:
        cid, aid, cdir, fn, ln, st = c
        if cdir and cdir in dirs_on_disk:
            continue
        if aid in aids_on_disk:
            continue
        # only flag if looks like AID profile import (optional filter)
        f.write(f"{cid}\t{aid}\t{cdir}\t{fn} {ln}\t{st}\n")
        n_db_miss += 1

partial_n = max(0, sum(1 for _ in partial.read_text(encoding="utf-8").splitlines()) - 1)

# Skills stats for matched
matched_with_skills = 0
matched_no_skills = 0
for i, line in enumerate(matched.read_text(encoding="utf-8").splitlines()):
    if i == 0:
        continue
    parts = line.split("\t")
    if len(parts) >= 7:
        if parts[6] == "1":
            matched_with_skills += 1
        else:
            matched_no_skills += 1

summary = f"""AID Disk vs DB Summary
======================
Letters:              $LETTERS
neu/cv PDF on disk:   {len(disk_rows)}
matched (dir|aid):    {n_ok}
disk NOT in DB:       {n_miss}
DB AID without neu:   {n_db_miss}
partial html/docx:    {partial_n}
matched + skills:     {matched_with_skills}
matched, 0 skills:    {matched_no_skills}
Consultants mit AID:  {len(cons)}

Files:
  {neu_tsv}
  {disk_not_db}
  {db_not_disk}
  {partial}
  {matched}
"""
(out / "summary.txt").write_text(summary, encoding="utf-8")
print(summary)

# Top letters in disk-not-in-db
from collections import Counter
c = Counter()
for i, line in enumerate(disk_not_db.read_text(encoding="utf-8").splitlines()):
    if i == 0 or not line.strip():
        continue
    c[line.split("\t")[0]] += 1
if c:
    print("disk-not-in-db by letter (top 15):")
    for k, v in c.most_common(15):
        print(f"  {k}: {v}")
PY

echo
echo "Ende: $(date -Iseconds)"
echo "OUT: $OUT"
echo "  cat $OUT/summary.txt"
