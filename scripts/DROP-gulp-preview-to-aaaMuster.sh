#!/usr/bin/env bash
# Kopiert die Cloud-Preview-PDF nach X:\Berater\AID_profile\aaaMuster
# Auf ucs5:
#   bash /mnt/public/udoo-reprap/scripts/DROP-gulp-preview-to-aaaMuster.sh
set -euo pipefail
REPO="${REPO:-/mnt/public/udoo-reprap}"
DEST="${DEST:-/mnt/public/Berater/AID_profile/aaaMuster}"
SRC="$REPO/artifacts/gulp-keyword/preview-aaaMuster"
mkdir -p "$DEST"
shopt -s nullglob
files=("$SRC"/AID-*-gulp-*.pdf "$SRC"/AID-*-gulp-*.html)
if ((${#files[@]} == 0)); then
  echo "FAIL: keine Preview-Dateien unter $SRC" >&2
  exit 1
fi
cp -v "${files[@]}" "$DEST/"
ls -la "$DEST"/AID-*-gulp-* 2>/dev/null | head -20
echo "OK → $DEST  (Windows: X:\\Berater\\AID_profile\\aaaMuster)"
