#!/usr/bin/env bash
# 10 zufällige alte AID-Profile → Pipeline → Compare Original vs neu/cv
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap
#   git pull origin cursor/cv-extractor-7f07
#   bash scripts/batch-aid-random10.sh
#
# Optional:
#   BATCH_N=10 SEED=42 SKIP_GOLDEN=1 bash scripts/batch-aid-random10.sh
#   DRY_RUN=1 bash scripts/batch-aid-random10.sh          # nur Manifest
#   IMPORT_ONLY=1 bash scripts/batch-aid-random10.sh      # ohne Compare
#   COMPARE_ONLY=1 bash scripts/batch-aid-random10.sh     # nur Compare (Manifest muss existieren)
#
set -euo pipefail

ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
OUT="${OUT:-$REPO/artifacts/aid-random10-$(date +%Y%m%d-%H%M%S)}"
MANIFEST="${MANIFEST:-$OUT/manifest.tsv}"
BATCH_N="${BATCH_N:-10}"
SEED="${SEED:-}"
SKIP_GOLDEN="${SKIP_GOLDEN:-1}"
DRY_RUN="${DRY_RUN:-0}"
IMPORT_ONLY="${IMPORT_ONLY:-0}"
COMPARE_ONLY="${COMPARE_ONLY:-0}"

SKIP_LETTERS='gulp_id Anfragen Auftragsbestätigung xxx zzzSONSTIGES aaa_low-level aaaMuster neu sch st __CheckInOut.exe __Share.url __ShowDetails.exe'
GOLDEN='troschke_thomas pfirrmann_peter vogelgesang_oliver'

mkdir -p "$OUT"

if [[ "$COMPARE_ONLY" != "1" ]]; then
  echo "=== Scan AID-Profile unter $ROOT ==="
  CAND="$OUT/candidates.tsv"
  : > "$CAND"

  for letter_dir in "$ROOT"/*; do
    [[ -d "$letter_dir" ]] || continue
    letter="$(basename "$letter_dir")"
    case " $SKIP_LETTERS " in *" $letter "*) continue ;; esac
    # nur 3-Buchstaben-Bucket (aaa…zzz)
    [[ "$letter" =~ ^[a-z]{3}$ ]] || continue

    for person_dir in "$letter_dir"/*; do
      [[ -d "$person_dir" ]] || continue
      dir="$(basename "$person_dir")"
      case "$dir" in
        neu|audit|ada|Neuer\ Ordner*) continue ;;
      esac
      if [[ "$SKIP_GOLDEN" == "1" ]]; then
        case " $GOLDEN " in *" $dir "*) continue ;; esac
      fi

      # neuesstes deutsches AID-*.pdf direkt im Person-Ordner
      pdf="$(
        find "$person_dir" -maxdepth 1 -type f -iname 'AID-*.pdf' \
          ! -iname '*engl*' ! -iname '*_en.*' ! -iname '*-en.*' \
          ! -iname '*_alt*' ! -iname '*löschen*' ! -iname '*loeschen*' \
          -printf '%T@\t%p\n' 2>/dev/null \
        | sort -nr | head -1 | cut -f2-
      )"
      [[ -n "$pdf" && -f "$pdf" ]] || continue
      printf '%s\t%s\t%s\n' "$letter" "$dir" "$pdf" >> "$CAND"
    done
  done

  total="$(wc -l < "$CAND" | tr -d ' ')"
  echo "Kandidaten: $total"
  if [[ "$total" -lt "$BATCH_N" ]]; then
    echo "ERROR: nur $total Kandidaten, brauche $BATCH_N" >&2
    exit 1
  fi

  # Random-Sample
  if [[ -n "$SEED" ]]; then
    SAMPLE="$(awk -v seed="$SEED" -v n="$BATCH_N" '
      BEGIN { srand(seed) }
      { lines[NR]=$0 }
      END {
        for (i=NR; i>1; i--) {
          j = int(rand()*i)+1
          tmp=lines[i]; lines[i]=lines[j]; lines[j]=tmp
        }
        for (i=1; i<=n && i<=NR; i++) print lines[i]
      }
    ' "$CAND")"
  else
    SAMPLE="$(shuf -n "$BATCH_N" "$CAND")"
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
    # IMPORT OK nur wenn neu/cv wirklich eine AID-PDF hat
    # (Pipeline-success ≠ Publish; siehe lorenz_michael Random-10)
    neu_pdf="$(
      find "$ROOT/$letter/$dir/neu/cv" -maxdepth 1 -type f -iname 'AID-*.pdf' \
        2>/dev/null | head -1
    )"
    if [[ -n "$neu_pdf" && -f "$neu_pdf" ]]; then
      echo "$letter	$dir	OK	$neu_pdf" >> "$OUT/import-ok.tsv"
    else
      echo "WARN: Pipeline/Import ohne neu/cv PDF: $letter/$dir" >&2
      # falscher Letter-Bucket? (Publish nutzt consultant_dir)
      wrong="$(
        find "$ROOT" -path "*/$dir/neu/cv/AID-*.pdf" 2>/dev/null | head -5
      )"
      if [[ -n "$wrong" ]]; then
        echo "  Hinweis: neu/cv woanders gefunden:" >&2
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

  # Score aus index.json ziehen falls vorhanden
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
echo "Scores:    $OUT/compare-scores.tsv"
echo "Details:   $COMPARE_ROOT/"
column -t -s $'\t' "$OUT/compare-scores.tsv" 2>/dev/null || cat "$OUT/compare-scores.tsv"
