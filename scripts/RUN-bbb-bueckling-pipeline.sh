#!/usr/bin/env bash
# Test: cleaned Gulp-PDF durch CV-Pipeline
# Ziel: X:\Berater\AID_profile\bbb\bueckling_joerg\neu\cv\AID-jb_n.n.n.n-…
#
# Auf ucs5 (nach SAFE-gulp-keywords.sh deploy):
#   bash /mnt/public/udoo-reprap/scripts/RUN-bbb-bueckling-pipeline.sh
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
LETTER="${LETTER:-bbb}"
DIR_NAME="${DIR_NAME:-bueckling_joerg}"
VERSION_TAG="${VERSION_TAG:-1.0.0.0}"
INI="${INI:-jb}"

PERSON="$ROOT/$LETTER/$DIR_NAME"
NEU="$PERSON/neu/cv"
# Sauberer AID-Name für get_best_pdf (ohne -gulp-Suffix)
SRC_PDF="${SRC_PDF:-}"
if [[ -z "$SRC_PDF" ]]; then
  SRC_PDF="$(ls -1 "$REPO"/artifacts/gulp-keyword/preview-aaaMuster/AID-${INI}_*-gulp-*.pdf 2>/dev/null | head -1 || true)"
fi
if [[ -z "$SRC_PDF" || ! -f "$SRC_PDF" ]]; then
  echo "FAIL: Preview-PDF fehlt. Erwartet unter artifacts/gulp-keyword/preview-aaaMuster/" >&2
  exit 1
fi

DEST_PDF="$PERSON/AID-${INI}_${VERSION_TAG}.pdf"

echo "=== bbb / $DIR_NAME Pipeline ==="
echo "SRC:  $SRC_PDF"
echo "DEST: $DEST_PDF"
echo "NEU:  $NEU"

mkdir -p "$PERSON" "$NEU"
chmod 0777 "$PERSON" "$PERSON/neu" "$NEU" 2>/dev/null || true

# Alte Test-AID-PDFs im Person-Root optional stehen lassen; Zielname überschreiben
cp -v "$SRC_PDF" "$DEST_PDF"
# Sidecars zur Kontrolle
cp -v "${SRC_PDF%.pdf}.txt" "$PERSON/" 2>/dev/null || true
cp -v "${SRC_PDF%.pdf}.experience.json" "$PERSON/" 2>/dev/null || true

ls -la "$PERSON"/AID-*.pdf

echo
echo "=== import_aid_profiles --sync ==="
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"

python3 manage.py import_aid_profiles \
  --letter "$LETTER" \
  --dir "$DIR_NAME" \
  --sync \
  --no-skip-existing

echo
echo "=== neu/cv ==="
ls -la "$NEU" || true
echo
echo "Windows: X:\\Berater\\AID_profile\\$LETTER\\$DIR_NAME\\neu\\cv\\"
find "$NEU" -maxdepth 1 -type f -iname 'AID-*.pdf' -printf '%f\n' 2>/dev/null | head -20
