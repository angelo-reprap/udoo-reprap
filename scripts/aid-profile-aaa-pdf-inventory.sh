#!/usr/bin/env bash
# Inventar: AID-PDFs unter AID_profile/aaa — gleiche Logik wie import get_best_pdf
#
# Auf ucs5:
#   bash /mnt/public/udoo-reprap/scripts/aid-profile-aaa-pdf-inventory.sh
#
set -euo pipefail

ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile/aaa}"

SKIP_PERSON='^(audit|neu|ada|Neuer Ordner.*)$'

if [[ ! -d "$ROOT" ]]; then
  echo "FEHLER: Root fehlt: $ROOT" >&2
  exit 1
fi

echo "# AID_profile/aaa — neuestes AID-PDF pro Berater (wie Import)"
echo "# Root: $ROOT"
echo "# Stand: $(date '+%Y-%m-%d %H:%M:%S')"
echo
printf '%-32s %-22s %-12s %s\n' "CONSULTANT_DIR" "AID_PDF" "MTIME" "NOTE"
printf '%-32s %-22s %-12s %s\n' "--------------------------------" "----------------------" "------------" "----"

count=0
no_pdf=0
for dir in "$ROOT"/*/; do
  [[ -d "$dir" ]] || continue
  name=$(basename "$dir")
  if [[ "$name" =~ $SKIP_PERSON ]]; then
    printf '%-32s %-22s %-12s %s\n' "$name" "—" "—" "SKIP"
    continue
  fi

  # nur direkte AID-*.pdf, deutsch, ohne _alt/löschen
  mapfile -t cands < <(
    find "$dir" -maxdepth 1 -type f -iname 'AID-*.pdf' -printf '%T@|%TY-%Tm-%Td|%f\n' 2>/dev/null \
      | grep -viE 'engl|_en\.|-en\.|_en_|englisch|_alt|löschen|loeschen' \
      | sort -t'|' -k1,1nr
  )

  if [[ ${#cands[@]} -eq 0 ]]; then
    printf '%-32s %-22s %-12s %s\n' "$name" "—" "—" "kein AID-PDF"
    no_pdf=$((no_pdf + 1))
    continue
  fi

  IFS='|' read -r _ts mtime fname <<<"${cands[0]}"
  note=""
  if [[ ${#cands[@]} -gt 1 ]]; then
    note="(+$(( ${#cands[@]} - 1 )) ältere)"
  fi
  printf '%-32s %-22s %-12s %s\n' "$name" "$fname" "$mtime" "$note"
  count=$((count + 1))
done

echo
echo "# Batch-Kandidaten: $count   ohne PDF: $no_pdf"
echo "# Start Overnight:"
echo "#   bash /mnt/public/udoo-reprap/scripts/aaa-overnight-batch.sh"
echo "# Test 3 sync:"
echo "#   bash /mnt/public/udoo-reprap/scripts/aaa-overnight-batch.sh --sync --limit 3 --force"
