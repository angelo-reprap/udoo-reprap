#!/usr/bin/env bash
# Inventar: AID-PDFs unter AID_profile/aaa (neuste zuerst)
#
# Auf ucs5:
#   bash /mnt/public/udoo-reprap/scripts/aid-profile-aaa-pdf-inventory.sh
#   # oder nur Listing:
#   bash …/aid-profile-aaa-pdf-inventory.sh --list
#
set -euo pipefail

ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile/aaa}"
MODE="${1:---list}"

if [[ ! -d "$ROOT" ]]; then
  echo "FEHLER: Root fehlt: $ROOT" >&2
  exit 1
fi

echo "# AID_profile/aaa PDF-Inventar"
echo "# Root: $ROOT"
echo "# Stand: $(date '+%Y-%m-%d %H:%M:%S')"
echo

# Alle PDFs, mtime absteigend (neuste oben)
# Format: mtime | size | pfad
mapfile -t ALL < <(
  find "$ROOT" -type f -iname '*.pdf' -printf '%T@|%TY-%Tm-%Td %TH:%TM|%s|%p\n' 2>/dev/null \
    | sort -t'|' -k1,1nr \
    | cut -d'|' -f2-
)

echo "## Alle PDFs (${#ALL[@]}), neueste zuerst"
echo
printf '%-16s %10s  %s\n' "MTIME" "BYTES" "PFAD"
printf '%-16s %10s  %s\n' "----------------" "----------" "----"
for line in "${ALL[@]}"; do
  IFS='|' read -r mtime size path <<<"$line"
  printf '%-16s %10s  %s\n' "$mtime" "$size" "$path"
done

echo
echo "## Pro Berater-Ordner: neuestes AID-*.pdf (Fallback: neuestes *.pdf)"
echo

# Berater-Ordner = direkte Kinder von aaa/
mapfile -t DIRS < <(find "$ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)

printf '%-28s %-18s %-12s %s\n' "CONSULTANT_DIR" "AID" "MTIME" "REL_PATH"
printf '%-28s %-18s %-12s %s\n' "----------------------------" "------------------" "------------" "--------"

for d in "${DIRS[@]}"; do
  dir="$ROOT/$d"
  # Bevorzugt AID-*.pdf irgendwo unter dem Ordner (inkl. alt/neu/cv)
  best=""
  best_mtime=0
  best_aid="—"
  while IFS= read -r -d '' f; do
    mt=$(stat -c '%Y' "$f" 2>/dev/null || echo 0)
    if (( mt >= best_mtime )); then
      best_mtime=$mt
      best=$f
      base=$(basename "$f")
      if [[ "$base" =~ ^(AID-[A-Za-z0-9_.-]+)\.pdf$ ]]; then
        best_aid="${BASH_REMATCH[1]}"
      else
        best_aid="(kein AID-Name)"
      fi
    fi
  done < <(find "$dir" -type f \( -iname 'AID-*.pdf' -o -iname '*.pdf' \) -print0 2>/dev/null)

  if [[ -z "$best" ]]; then
    printf '%-28s %-18s %-12s %s\n' "$d" "—" "—" "(kein PDF)"
    continue
  fi
  rel="${best#"$ROOT"/}"
  mstr=$(date -d "@$best_mtime" '+%Y-%m-%d' 2>/dev/null || echo "?")
  printf '%-28s %-18s %-12s %s\n' "$d" "$best_aid" "$mstr" "$rel"
done

echo
echo "# Fertig. Für Batch-Konvertierung später: nur Zeilen mit AID-*.pdf als Input."
