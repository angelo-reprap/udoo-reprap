#!/usr/bin/env bash
# Kopiert die 10er-Batch neu/cv (+ Quell-PDF + gulp_profil_c TXT) ins Repo
# zur Review durch den Cloud-Agent (Quelle TXT vs Ziel PDF/extracted).
#
# Auf ucs5 — empfohlen in einem Rutsch nach dem Batch:
#
#   RESULT_TSV=$(ls -td /tmp/gulp-batch-*/result.tsv | head -1)
#   RESULT_TSV="$RESULT_TSV" bash scripts/EXPORT-gulp-batch-source-txt.sh
#   RESULT_TSV="$RESULT_TSV" bash scripts/SYNC-gulp-batch-neu-to-repo.sh
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
AID_ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"
BRANCH="${BRANCH:-cursor/gulp-keyword-pipeline-1532}"
RESULT_TSV="${RESULT_TSV:-}"
SOURCE_TXT="${SOURCE_TXT:-}"
OUT_REL="${OUT_REL:-artifacts/gulp-batch-review}"
DO_PUSH="${DO_PUSH:-1}"

cd "$REPO"
git fetch origin "$BRANCH" 2>/dev/null || true
git checkout "$BRANCH" 2>/dev/null || true
git pull origin "$BRANCH" 2>/dev/null || true

if [[ -z "$RESULT_TSV" ]]; then
  RESULT_TSV="$(ls -td /tmp/gulp-batch-*/result.tsv 2>/dev/null | head -1 || true)"
fi
if [[ -z "$RESULT_TSV" || ! -f "$RESULT_TSV" ]]; then
  echo "FAIL: RESULT_TSV fehlt. Setze RESULT_TSV=/tmp/gulp-batch-…/result.tsv" >&2
  exit 1
fi

if [[ -z "$SOURCE_TXT" ]]; then
  SOURCE_TXT="$(dirname "$RESULT_TSV")/source-txt"
fi

STAMP="$(basename "$(dirname "$RESULT_TSV")")"
OUT="$REPO/$OUT_REL/$STAMP"
mkdir -p "$OUT"
cp -a "$RESULT_TSV" "$OUT/result.tsv"
[[ -f "$(dirname "$RESULT_TSV")/summary.json" ]] && cp -a "$(dirname "$RESULT_TSV")/summary.json" "$OUT/"
[[ -f "$(dirname "$RESULT_TSV")/batch.log" ]] && \
  tail -n 400 "$(dirname "$RESULT_TSV")/batch.log" >"$OUT/batch.log.tail.txt" || true

echo "RESULT_TSV=$RESULT_TSV"
echo "SOURCE_TXT=$SOURCE_TXT"
echo "OUT=$OUT"
echo

n=0
while IFS=$'\t' read -r status contact_id gulp_id letter dir pdf note secs || [[ -n "${status:-}" ]]; do
  [[ "${status:-}" == "status" || -z "${status:-}" ]] && continue
  [[ "$status" != "OK" && "$status" != "FAIL" ]] && continue
  [[ -z "${letter:-}" || -z "${dir:-}" ]] && continue

  person="$AID_ROOT/$letter/$dir"
  neu="$person/neu/cv"
  dest="$OUT/$letter/$dir"
  mkdir -p "$dest/neu/cv" "$dest/source"

  echo "── $status $letter/$dir"
  if [[ -d "$neu" ]]; then
    find "$neu" -maxdepth 1 -type f \( \
      -iname 'AID-*.pdf' -o -iname 'AID-*.html' -o -iname 'AID-*.docx' \
    \) -exec cp -a {} "$dest/neu/cv/" \;
    echo "  neu/cv: $(ls "$dest/neu/cv" 2>/dev/null | wc -l) Dateien"
  else
    echo "  WARN: kein neu/cv"
  fi
  find "$person" -maxdepth 1 -type f -iname 'AID-*.pdf' -exec cp -a {} "$dest/source/" \; 2>/dev/null || true

  src_txt=""
  if [[ -f "$SOURCE_TXT/by-person/$letter/$dir/gulp_profil_c.txt" ]]; then
    src_txt="$SOURCE_TXT/by-person/$letter/$dir/gulp_profil_c.txt"
  elif [[ -f "$SOURCE_TXT/txt/${letter}__${dir}.txt" ]]; then
    src_txt="$SOURCE_TXT/txt/${letter}__${dir}.txt"
  elif [[ -f "$REPO/artifacts/gulp-samples/txt/${dir}.txt" ]]; then
    src_txt="$REPO/artifacts/gulp-samples/txt/${dir}.txt"
  fi
  if [[ -n "$src_txt" ]]; then
    cp -a "$src_txt" "$dest/source/gulp_profil_c.txt"
    echo "  source TXT: $(wc -c <"$dest/source/gulp_profil_c.txt") bytes"
  else
    echo "  WARN: kein gulp_profil_c.txt (EXPORT vorher laufen lassen)"
  fi

  conv="$(dirname "$RESULT_TSV")/convert-$dir"
  if [[ -d "$conv" ]]; then
    mkdir -p "$dest/convert-log"
    cp -a "$conv"/* "$dest/convert-log/" 2>/dev/null || true
  fi
  if [[ -d /opt/abpe/backend/data/extracted/"$dir" ]]; then
    mkdir -p "$dest/extracted"
    find /opt/abpe/backend/data/extracted/"$dir" -maxdepth 1 -name 'AID-*.txt' \
      -exec cp -a {} "$dest/extracted/" \; 2>/dev/null || true
  fi
  n=$((n + 1))
done <"$RESULT_TSV"

{
  echo "# Gulp-Batch Review $STAMP"
  echo
  echo "Quelle: \`$RESULT_TSV\`"
  echo "DB-TXT: \`$SOURCE_TXT\`"
  echo "Kopiert: $n Einträge"
  echo
  echo "Pro Person:"
  echo "- \`source/gulp_profil_c.txt\` — CRM Rohtext (Quelle)"
  echo "- \`source/AID-*_1.0.0.0.pdf\` — Convert-PDF"
  echo "- \`neu/cv/AID-*.pdf\` — Pipeline-Ziel"
  echo "- \`extracted/AID-*.txt\` — Pipeline-Extrakt"
  echo
  echo "| Status | Letter/Dir | neu/cv PDF | Quelle TXT |"
  echo "|--------|------------|------------|------------|"
  while IFS=$'\t' read -r status _ _ letter dir pdf _; do
    [[ "$status" == "status" ]] && continue
    [[ "$status" != "OK" && "$status" != "FAIL" ]] && continue
    has_txt="—"
    [[ -f "$OUT/$letter/$dir/source/gulp_profil_c.txt" ]] && has_txt="ja"
    echo "| $status | \`$letter/$dir\` | ${pdf:-—} | $has_txt |"
  done <"$RESULT_TSV"
} >"$OUT/README.md"

echo
echo "Fertig: $n Profile → $OUT_REL/$STAMP"
git add "$OUT_REL/$STAMP"
if git diff --cached --quiet; then
  echo "Nichts Neues zu committen."
  exit 0
fi
git commit -m "chore: gulp-batch review $STAMP ($n Profile + Quelle-TXT)"
if [[ "$DO_PUSH" == "1" ]]; then
  if git push -u origin "$BRANCH"; then
    echo "OK gepusht → Cloud kann pullen"
  else
    echo "WARN: push fehlgeschlagen — manuell: git push origin $BRANCH" >&2
  fi
else
  echo "DO_PUSH=0 — bitte: git push origin $BRANCH"
fi
