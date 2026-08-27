#!/usr/bin/env bash
# ucs5: Office-Share (O:) vs Public (X:) für den EDMS-Viewer prüfen.
#
#   bash scripts/PROBE-edms-office-share.sh
#
set -euo pipefail
OFFICE="${DMS_OFFICE_MOUNT:-/mnt/office}"
PUBLIC="${DMS_PUBLIC_MOUNT:-/mnt/public}"
REL='Berater/Berater aktive & passive/passive/wollschlaeger_andreas/Rechnungen/Rechnung Hotel Schlossberg Wolli_Dezember2014.pdf'
FILE="$OFFICE/$REL"

echo "whoami=$(whoami)  id=$(id -u)/$(id -g) $(id -un 2>/dev/null || true)"
echo
for m in "$OFFICE" "$PUBLIC"; do
  echo "=== $m ==="
  if [[ -d "$m" ]]; then
    ls -ld "$m"
    echo -n "listdir: "
    ls "$m" >/dev/null 2>&1 && echo OK || echo FAIL
  else
    echo "FEHLT"
  fi
  echo
done

echo "=== Rechnungs-PDF ==="
echo "$FILE"
if [[ -f "$FILE" ]]; then
  ls -l "$FILE"
  echo -n "readable: "
  [[ -r "$FILE" ]] && echo YES || echo NO
else
  echo "nicht als Datei sichtbar"
  parent=$(dirname "$FILE")
  echo "parent: $parent"
  if [[ -d "$parent" ]]; then
    ls -ld "$parent"
    ls -la "$parent" | head -20
  else
    echo "Parent fehlt — Ordnernamen mit '&' prüfen:"
    ls -la "$OFFICE/Berater" 2>/dev/null | head -20 || echo "  $OFFICE/Berater fehlt"
  fi
fi

if command -v namei >/dev/null 2>&1; then
  echo
  echo "=== namei ==="
  namei -l "$FILE" || true
fi
