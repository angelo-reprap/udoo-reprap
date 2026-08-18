#!/usr/bin/env bash
# Kurzer Status: läuft der AID letter-Batch noch / warum still?
#
#   cd /mnt/public/udoo-reprap
#   bash scripts/diagnose-aid-batch-status.sh
#   LETTER=bbb bash scripts/diagnose-aid-batch-status.sh
#
set -euo pipefail

LETTER="${LETTER:-bbb}"
AID_ROOT="${AID_ROOT:-/mnt/public/Berater/AID_profile}"
BASE="$AID_ROOT/$LETTER"

echo "======== AID Batch Status LETTER=$LETTER ========"
echo "BASE=$BASE"

if [[ ! -d "$BASE" ]]; then
  echo "FEHLER: Ordner fehlt"
  exit 1
fi

total=$(find "$BASE" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
with_neu=$(find "$BASE" -path '*/neu/cv/AID-*.pdf' 2>/dev/null | wc -l)
dirs_with_neu=$(find "$BASE" -path '*/neu/cv/AID-*.pdf' -printf '%h\n' 2>/dev/null | sed 's#/neu/cv##' | sort -u | wc -l)

echo "Consultant-Ordner:     $total"
echo "neu/cv AID-PDFs:       $with_neu"
echo "Ordner mit neu/cv:     $dirs_with_neu"
echo "Noch ohne neu/cv:      $(( total - dirs_with_neu ))"

echo
echo "── letzte neu/cv PDFs ──"
find "$BASE" -path '*/neu/cv/AID-*.pdf' -printf '%T+ %p\n' 2>/dev/null \
  | sort -r | head -8 || true

echo
echo "── laufende Import-/Celery-Prozesse ──"
pgrep -af 'import_aid_profiles|batch-aid-letter|celery|main_pipeline' 2>/dev/null | head -20 || echo "(keine)"

echo
echo "── OnlyOffice pluginsmanager (RAM-Killer)? ──"
pgrep -af 'tools/pluginsmanager|documentserver-pluginsmanager' 2>/dev/null | head -5 || echo "(ok, keiner)"

echo
echo "── RAM ──"
free -h | head -2

echo
echo "Weiter (wenn still):"
echo "  LETTER=$LETTER SKIP_EXISTING_NEU=1 LIMIT=5 bash scripts/batch-aid-letter.sh"
echo "  # oder detach:"
echo "  LETTER=$LETTER SKIP_EXISTING_NEU=1 LIMIT=5 bash scripts/batch-aid-letter-detach.sh"
