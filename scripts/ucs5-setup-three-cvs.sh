#!/usr/bin/env bash
# Auf ucs5 ausführen (nicht catten — direkt bash/python).
# Golden-Set: troschke_thomas, pfirrmann_peter, vogelgesang_oliver
set -euo pipefail

ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"
BACKEND="${BACKEND:-/opt/abpe/backend}"

echo "=== mkdir neu/cv ==="
for spec in \
  "ttt:troschke_thomas" \
  "ppp:pfirrmann_peter" \
  "vvv:vogelgesang_oliver"
do
  letter="${spec%%:*}"
  dir="${spec##*:}"
  target="$ROOT/$letter/$dir/neu/cv"
  mkdir -p "$target"
  chmod 0777 "$ROOT/$letter/$dir/neu" "$target" 2>/dev/null || true
  echo "OK $target (exists=$([[ -d $target ]] && echo yes || echo no))"
  # Quell-PDF im Person-Ordner prüfen
  person="$ROOT/$letter/$dir"
  echo "  PDFs im Person-Ordner:"
  ls -la "$person"/AID-*.pdf 2>/dev/null | head -5 || echo "  ⚠ kein AID-*.pdf in $person"
done

echo
echo "=== Import (sync) — aus $BACKEND ==="
cd "$BACKEND"
for spec in \
  "ttt:troschke_thomas" \
  "ppp:pfirrmann_peter" \
  "vvv:vogelgesang_oliver"
do
  letter="${spec%%:*}"
  dir="${spec##*:}"
  echo ">>> import $letter / $dir"
  python3 manage.py import_aid_profiles \
    --letter "$letter" --dir "$dir" --sync --no-skip-existing
  echo ">>> neu/cv nach Import:"
  ls -la "$ROOT/$letter/$dir/neu/cv/" | tail -20
  echo
done

echo "Fertig."
