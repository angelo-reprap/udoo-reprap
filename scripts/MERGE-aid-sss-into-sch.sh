#!/usr/bin/env bash
# MERGE: AID_profile/sss/<name>/ → AID_profile/sch/<name>/ für exakte Namens-Paare,
# danach sss/<name>/ löschen.
#
# Nur wenn nachname_vorname in sch/ und sss/ **gleich** (Ordnername 1:1).
# Kopiert Diff: fehlende Dateien/Ordner aus sss nach sch (--ignore-existing),
# erzwingt zusätzlich neu/ (Publish-Stand). Bestehende Originale in sch bleiben.
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/aid-sch-sss-dupes-1532
#   git checkout cursor/aid-sch-sss-dupes-1532
#
#   # Dry-Run (default):
#   bash scripts/MERGE-aid-sss-into-sch.sh
#
#   # Ein Profil testen:
#   LIMIT=1 NAME=schaefer_arno bash scripts/MERGE-aid-sss-into-sch.sh
#   LIMIT=1 NAME=schaefer_arno EXECUTE=1 bash scripts/MERGE-aid-sss-into-sch.sh
#
#   # Alle Paare:
#   EXECUTE=1 bash scripts/MERGE-aid-sss-into-sch.sh
#
set -euo pipefail

ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"
SCH="$ROOT/sch"
SSS="$ROOT/sss"
OUT="${OUT:-/tmp/aid-merge-sss-into-sch-$(date +%Y%m%d-%H%M%S)}"
EXECUTE="${EXECUTE:-0}"
LIMIT="${LIMIT:-0}"
NAME="${NAME:-}"
# Wenn 1: bei Verify-Fehler sss-Ordner nicht löschen (immer so — Safety)
REQUIRE_NEU_PDF="${REQUIRE_NEU_PDF:-1}"

mkdir -p "$OUT"
LOG="$OUT/merge.log"
REPORT="$OUT/report.tsv"
SKIP="$OUT/skipped.tsv"

echo "======== MERGE sss → sch (exact name pairs) ========" | tee "$LOG"
echo "Start: $(date -Iseconds)" | tee -a "$LOG"
echo "SCH=$SCH" | tee -a "$LOG"
echo "SSS=$SSS" | tee -a "$LOG"
echo "OUT=$OUT" | tee -a "$LOG"
echo "EXECUTE=$EXECUTE LIMIT=$LIMIT NAME=${NAME:-*}" | tee -a "$LOG"
echo | tee -a "$LOG"

if [[ ! -d "$SCH" ]]; then
  echo "FAIL: $SCH fehlt" | tee -a "$LOG"
  exit 1
fi
if [[ ! -d "$SSS" ]]; then
  echo "FAIL: $SSS fehlt" | tee -a "$LOG"
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "FAIL: rsync fehlt" | tee -a "$LOG"
  exit 1
fi

python3 - <<'PY' "$SCH" "$SSS" "$OUT" "$NAME" "$LIMIT"
import os, sys, json
from pathlib import Path

sch_root = Path(sys.argv[1])
sss_root = Path(sys.argv[2])
out = Path(sys.argv[3])
name_filter = (sys.argv[4] or "").strip()
limit = int(sys.argv[5] or "0")

skip_names = {"neu", "audit", "ada"}


def list_person_dirs(root: Path) -> dict[str, Path]:
    d = {}
    for p in root.iterdir():
        if not p.is_dir():
            continue
        if p.name in skip_names or p.name.startswith("Neuer"):
            continue
        d[p.name] = p
    return d


sch = list_person_dirs(sch_root)
sss = list_person_dirs(sss_root)
both = sorted(set(sch) & set(sss), key=str.lower)

if name_filter:
    both = [n for n in both if n == name_filter]
    if not both:
        # case-insensitive fallback for NAME=
        both = [n for n in sorted(set(sch) & set(sss)) if n.lower() == name_filter.lower()]

if limit > 0:
    both = both[:limit]

pairs = [{"name": n, "sch": str(sch[n]), "sss": str(sss[n])} for n in both]
(out / "pairs.json").write_text(json.dumps(pairs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(out / "pair_names.txt").write_text("\n".join(n for n in both) + ("\n" if both else ""), encoding="utf-8")
print(f"pairs={len(pairs)}")
if name_filter and not both:
    print(f"WARN: NAME={name_filter!r} nicht in exact overlap", file=sys.stderr)
    sys.exit(2)
PY

PAIR_COUNT=$(python3 -c "import json; print(len(json.load(open('$OUT/pairs.json'))))")
echo "Exact-name pairs to process: $PAIR_COUNT" | tee -a "$LOG"
echo -e "name\taction\tsch_neu_before\tsss_neu\tcopied_files\tsch_neu_after\tsss_deleted\tstatus\tnote" > "$REPORT"
echo -e "name\treason" > "$SKIP"

ok=0
fail=0
dry=0

has_neu_pdf() {
  local d="$1"
  local neu="$d/neu/cv"
  [[ -d "$neu" ]] || return 1
  local f
  shopt -s nullglob
  for f in "$neu"/AID-*.pdf "$neu"/AID-*.PDF; do
    [[ -f "$f" ]] && return 0
  done
  return 1
}

count_rel_files() {
  # relative file paths under dir (files only)
  local d="$1"
  find "$d" -type f | sed "s|^$d/||" | sort
}

verify_sss_subset_in_sch() {
  local sch_dir="$1"
  local sss_dir="$2"
  local missing=0
  local rel
  while IFS= read -r rel; do
    [[ -z "$rel" ]] && continue
    if [[ ! -e "$sch_dir/$rel" ]]; then
      echo "MISSING_IN_SCH: $rel" >&2
      missing=$((missing + 1))
    fi
  done < <(count_rel_files "$sss_dir")
  [[ "$missing" -eq 0 ]]
}

while IFS= read -r name; do
  [[ -z "$name" ]] && continue
  sch_dir="$SCH/$name"
  sss_dir="$SSS/$name"

  if [[ ! -d "$sch_dir" || ! -d "$sss_dir" ]]; then
    echo -e "$name\tmissing_dir" >> "$SKIP"
    echo "SKIP $name (dir fehlt)" | tee -a "$LOG"
    fail=$((fail + 1))
    continue
  fi

  sch_neu_b=0
  sss_neu=0
  has_neu_pdf "$sch_dir" && sch_neu_b=1
  has_neu_pdf "$sss_dir" && sss_neu=1

  # Diff preview: files in sss not in sch
  mapfile -t NEW_FILES < <(
    comm -23 \
      <(count_rel_files "$sss_dir") \
      <(count_rel_files "$sch_dir")
  )
  copied_n=${#NEW_FILES[@]}

  if [[ "$EXECUTE" != "1" ]]; then
    echo "DRY $name  new_files=$copied_n  sss_neu=$sss_neu sch_neu=$sch_neu_b" | tee -a "$LOG"
    if [[ "$copied_n" -gt 0 && "$copied_n" -le 8 ]]; then
      for f in "${NEW_FILES[@]}"; do
        echo "     + $f" | tee -a "$LOG"
      done
    elif [[ "$copied_n" -gt 8 ]]; then
      for f in "${NEW_FILES[@]:0:5}"; do
        echo "     + $f" | tee -a "$LOG"
      done
      echo "     … +$((copied_n - 5)) more" | tee -a "$LOG"
    fi
    echo -e "$name\tdry-run\t$sch_neu_b\t$sss_neu\t$copied_n\t-\t0\tok\t" >> "$REPORT"
    dry=$((dry + 1))
    continue
  fi

  echo ">>> MERGE $name (new_files≈$copied_n)" | tee -a "$LOG"

  # 1) Diff: fehlende Dateien (Originale in sch nicht überschreiben)
  rsync -a --ignore-existing "$sss_dir/" "$sch_dir/" >>"$LOG" 2>&1

  # 2) neu/ immer aus sss nachziehen (Publish-Stand; Update erlaubt)
  if [[ -d "$sss_dir/neu" ]]; then
    mkdir -p "$sch_dir/neu"
    rsync -a "$sss_dir/neu/" "$sch_dir/neu/" >>"$LOG" 2>&1
  fi

  sch_neu_a=0
  has_neu_pdf "$sch_dir" && sch_neu_a=1

  note=""
  status="ok"
  if [[ "$REQUIRE_NEU_PDF" == "1" && "$sss_neu" == "1" && "$sch_neu_a" != "1" ]]; then
    status="fail"
    note="neu_pdf_missing_after_copy"
  fi

  if [[ "$status" == "ok" ]]; then
    if ! verify_sss_subset_in_sch "$sch_dir" "$sss_dir" 2>>"$LOG"; then
      status="fail"
      note="sss_files_not_all_in_sch"
    fi
  fi

  deleted=0
  if [[ "$status" == "ok" ]]; then
    rm -rf --one-file-system "$sss_dir"
    if [[ -d "$sss_dir" ]]; then
      status="fail"
      note="sss_delete_failed"
    else
      deleted=1
    fi
  else
    echo "KEEP sss/$name ($note)" | tee -a "$LOG"
  fi

  echo -e "$name\tmerge\t$sch_neu_b\t$sss_neu\t$copied_n\t$sch_neu_a\t$deleted\t$status\t$note" >> "$REPORT"
  if [[ "$status" == "ok" ]]; then
    echo "OK   $name  neu=$sch_neu_a deleted_sss=$deleted" | tee -a "$LOG"
    ok=$((ok + 1))
  else
    echo "FAIL $name  $note" | tee -a "$LOG"
    fail=$((fail + 1))
  fi
done < "$OUT/pair_names.txt"

# Post-check: remaining exact overlaps
REMAIN=$(python3 - <<'PY' "$SCH" "$SSS"
from pathlib import Path
import sys
sch = {p.name for p in Path(sys.argv[1]).iterdir() if p.is_dir() and p.name not in {"neu","audit","ada"} and not p.name.startswith("Neuer")}
sss = {p.name for p in Path(sys.argv[2]).iterdir() if p.is_dir() and p.name not in {"neu","audit","ada"} and not p.name.startswith("Neuer")}
print(len(sch & sss))
PY
)

SUMMARY="$OUT/summary.json"
python3 - <<PY
import json
from pathlib import Path
out = Path("$OUT")
summary = {
  "execute": "$EXECUTE" == "1",
  "pairs": int("$PAIR_COUNT"),
  "ok": int("$ok"),
  "fail": int("$fail"),
  "dry": int("$dry"),
  "remaining_exact_overlap": int("$REMAIN"),
  "report": str(out / "report.tsv"),
  "log": str(out / "merge.log"),
}
(out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
PY

echo | tee -a "$LOG"
echo "Fertig: $OUT" | tee -a "$LOG"
echo "remaining exact overlap sch∩sss: $REMAIN" | tee -a "$LOG"
ls -la "$OUT" | tee -a "$LOG"

if [[ "$EXECUTE" == "1" && "$fail" -gt 0 ]]; then
  exit 1
fi
