#!/usr/bin/env bash
# Alle neuesten AID-*.pdf unter einem Letter-Bucket → Pipeline (sync) → Compare
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap
#   git pull --rebase origin cursor/cv-extractor-7f07
#   bash scripts/SAFE-cv-extractor-edit.sh deploy
#
# Smoke (3 Stück):
#   LETTER=bbb LIMIT=3 bash scripts/batch-aid-letter.sh
#
# Alles unter bbb (detached empfohlen — dauert):
#   LETTER=bbb bash scripts/batch-aid-letter-detach.sh
#
# Nur Manifest:
#   LETTER=bbb DRY_RUN=1 bash scripts/batch-aid-letter.sh
#
# Nur Compare (Manifest muss existieren):
#   LETTER=bbb MANIFEST=artifacts/aid-bbb-…/manifest.tsv COMPARE_ONLY=1 bash scripts/batch-aid-letter.sh
#
set -euo pipefail

LETTER="${LETTER:-bbb}"
LETTER="$(echo "$LETTER" | tr '[:upper:]' '[:lower:]')"
ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
OUT="${OUT:-$REPO/artifacts/aid-${LETTER}-$(date +%Y%m%d-%H%M%S)}"
MANIFEST="${MANIFEST:-$OUT/manifest.tsv}"
LIMIT="${LIMIT:-0}"
DRY_RUN="${DRY_RUN:-0}"
IMPORT_ONLY="${IMPORT_ONLY:-0}"
COMPARE_ONLY="${COMPARE_ONLY:-0}"
SKIP_EXISTING_NEU="${SKIP_EXISTING_NEU:-0}"  # 1 = Dirs mit neu/cv AID-pdf überspringen

if [[ ! "$LETTER" =~ ^[a-z]{3}$ ]]; then
  echo "ERROR: LETTER muss 3 Kleinbuchstaben sein (z.B. bbb), got: $LETTER" >&2
  exit 1
fi

LETTER_DIR="$ROOT/$LETTER"
if [[ ! -d "$LETTER_DIR" ]]; then
  echo "ERROR: Letter-Ordner fehlt: $LETTER_DIR" >&2
  exit 1
fi

mkdir -p "$OUT"

if [[ "$COMPARE_ONLY" != "1" ]]; then
  echo "=== Scan $LETTER_DIR (neuestes AID-*.pdf pro nachname_vorname) ==="
  CAND="$OUT/candidates.tsv"
  : > "$CAND"
  skip_n=0

  for person_dir in "$LETTER_DIR"/*; do
    [[ -d "$person_dir" ]] || continue
    dir="$(basename "$person_dir")"
    case "$dir" in
      neu|audit|ada|Neuer\ Ordner*) continue ;;
    esac

    if [[ "$SKIP_EXISTING_NEU" == "1" ]]; then
      # -quit: kein SIGPIPE/pipefail-Abbruch wenn mehrere AID-*.pdf existieren
      existing="$(
        find "$person_dir/neu/cv" -maxdepth 1 -type f -iname 'AID-*.pdf' \
          -print -quit 2>/dev/null || true
      )"
      if [[ -n "$existing" ]]; then
        skip_n=$((skip_n + 1))
        continue
      fi
    fi

    pdf="$(
      find "$person_dir" -maxdepth 1 -type f -iname 'AID-*.pdf' \
        ! -iname '*engl*' ! -iname '*_en.*' ! -iname '*-en.*' \
        ! -iname '*_alt*' ! -iname '*löschen*' ! -iname '*loeschen*' \
        -printf '%T@\t%p\n' 2>/dev/null \
      | sort -nr | head -1 | cut -f2- || true
    )"
    [[ -n "$pdf" && -f "$pdf" ]] || continue
    printf '%s\t%s\t%s\n' "$LETTER" "$dir" "$pdf" >> "$CAND"
  done

  if [[ "$SKIP_EXISTING_NEU" == "1" ]]; then
    echo "Übersprungen (neu/cv schon da): $skip_n"
  fi

  total="$(wc -l < "$CAND" | tr -d ' ')"
  echo "Kandidaten: $total"
  if [[ "$total" -lt 1 ]]; then
    echo "ERROR: keine AID-PDFs unter $LETTER_DIR" >&2
    exit 1
  fi

  if [[ "$LIMIT" -gt 0 ]]; then
    SAMPLE="$(head -n "$LIMIT" "$CAND")"
    echo "LIMIT=$LIMIT → $(printf '%s\n' "$SAMPLE" | wc -l | tr -d ' ') Profile"
  else
    SAMPLE="$(cat "$CAND")"
  fi

  {
    echo -e "letter\tdir\torig_pdf"
    printf '%s\n' "$SAMPLE"
  } > "$MANIFEST"
  echo "Manifest → $MANIFEST"
  column -t -s $'\t' "$MANIFEST" || cat "$MANIFEST"
fi

if [[ ! -f "$MANIFEST" ]]; then
  echo "ERROR: Manifest fehlt: $MANIFEST" >&2
  exit 1
fi

if [[ "$DRY_RUN" == "1" ]]; then
  echo "DRY_RUN=1 — stoppe vor Import"
  exit 0
fi

if [[ "$COMPARE_ONLY" != "1" ]]; then
  echo
  echo "=== Import (sync, no-skip) ==="
  cd "$BACKEND"
  # shellcheck disable=SC1091
  [[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate

  : > "$OUT/import-ok.tsv"
  : > "$OUT/import-failures.tsv"

  tail -n +2 "$MANIFEST" | while IFS=$'\t' read -r letter dir pdf; do
    [[ -n "$letter" && -n "$dir" ]] || continue
    echo
    echo ">>> IMPORT $letter/$dir  ($pdf)"
    if ! python3 manage.py import_aid_profiles \
      --letter "$letter" --dir "$dir" \
      --sync --no-skip-existing; then
      echo "WARN: Import fehlgeschlagen: $letter/$dir" >&2
      echo "$letter	$dir	FAIL" >> "$OUT/import-failures.tsv"
      continue
    fi
    neu_pdf="$(
      find "$ROOT/$letter/$dir/neu/cv" -maxdepth 1 -type f -iname 'AID-*.pdf' \
        2>/dev/null | head -1
    )"
    if [[ -n "$neu_pdf" && -f "$neu_pdf" ]]; then
      echo "$letter	$dir	OK	$neu_pdf" >> "$OUT/import-ok.tsv"
    else
      echo "WARN: kein neu/cv PDF: $letter/$dir" >&2
      wrong="$(
        find "$ROOT" -path "*/$dir/neu/cv/AID-*.pdf" 2>/dev/null | head -5
      )"
      if [[ -n "$wrong" ]]; then
        echo "$wrong" | sed 's/^/    /' >&2
        echo "$letter	$dir	FAIL_WRONG_BUCKET	$wrong" >> "$OUT/import-failures.tsv"
      else
        echo "$letter	$dir	FAIL_NO_NEU" >> "$OUT/import-failures.tsv"
      fi
    fi
  done
fi

if [[ "$IMPORT_ONLY" == "1" ]]; then
  echo "IMPORT_ONLY=1 — skip Compare"
  exit 0
fi

echo
echo "=== Compare Original vs neu/cv ==="
cd "$BACKEND"
COMPARE_ROOT="$OUT/compare"
mkdir -p "$COMPARE_ROOT"
: > "$OUT/compare-scores.tsv"
echo -e "letter\tdir\tscore\tstatus\tflags" >> "$OUT/compare-scores.tsv"

tail -n +2 "$MANIFEST" | while IFS=$'\t' read -r letter dir pdf; do
  [[ -n "$letter" && -n "$dir" ]] || continue
  echo
  echo ">>> COMPARE $letter/$dir"
  dest="$COMPARE_ROOT/${letter}_${dir}"
  python3 manage.py compare_aid_neu_cv \
    --letter "$letter" --dir "$dir" --out "$dest" || true

  idx="$dest/index.json"
  if [[ -f "$idx" ]]; then
    python3 - <<PY >> "$OUT/compare-scores.tsv"
import json
from pathlib import Path
p = Path("$idx")
data = json.loads(p.read_text(encoding="utf-8"))
rows = data if isinstance(data, list) else data.get("rows") or data.get("results") or []
if isinstance(data, dict) and "dir" in data:
    rows = [data]
for r in rows:
    if r.get("dir") != "$dir" and len(rows) > 1:
        continue
    flags = ";".join(r.get("flags") or [])
    print(f"$letter\t$dir\t{r.get('score')}\t{r.get('status')}\t{flags}")
    break
else:
    print("$letter\t$dir\t?\tno_row\t")
PY
  else
    echo -e "$letter\t$dir\t?\tno_index\t" >> "$OUT/compare-scores.tsv"
  fi
done

echo
echo "======== FERTIG ========"
echo "OUT:       $OUT"
echo "Manifest:  $MANIFEST"
echo "OK:        $OUT/import-ok.tsv"
echo "FAIL:      $OUT/import-failures.tsv"
echo "Scores:    $OUT/compare-scores.tsv"
column -t -s $'\t' "$OUT/compare-scores.tsv" 2>/dev/null || cat "$OUT/compare-scores.tsv"
echo
ok_n="$(wc -l < "$OUT/import-ok.tsv" 2>/dev/null | tr -d ' ' || echo 0)"
fail_n="$(wc -l < "$OUT/import-failures.tsv" 2>/dev/null | tr -d ' ' || echo 0)"
echo "Import OK=$ok_n  FAIL=$fail_n"
