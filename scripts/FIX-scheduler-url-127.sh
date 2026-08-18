#!/usr/bin/env bash
# Live: SCHEDULER URLs von localhost → 127.0.0.1 (IPv6/Timeout-Falle).
# Schreibt NUR wenn APPLY=1. Default = Dry-Run + Ort der Settings finden.
#
#   bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/FIX-scheduler-url-127.sh)
#   APPLY=1 bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/FIX-scheduler-url-127.sh)
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
APPLY="${APPLY:-0}"
TS=$(date +%Y%m%d-%H%M%S)

echo "======== FIX scheduler URL localhost→127.0.0.1 APPLY=$APPLY ========"

echo "=== Treffer in Settings ==="
rg -n 'SCHEDULER_API_BASE_URL|SHADULER_CALLBACK_BASE_URL|localhost:8000' \
  "$BACKEND" \
  --glob '*.py' --glob '*.env' --glob '*.json' --glob '*.yml' --glob '*.yaml' \
  -g '!**/__pycache__/**' -g '!**/migrations/**' 2>/dev/null | head -40 || true

echo
echo "Empfohlen (Live-Settings):"
echo "  SCHEDULER_API_BASE_URL = 'http://127.0.0.1:8000/scheduler/api'"
echo "  SHADULER_CALLBACK_BASE_URL = 'http://127.0.0.1:8000/shaduler/api'"
echo
echo "Danach:"
echo "  cd $BACKEND && /opt/abpe/venv311/bin/python manage.py register_scheduler_jobs"
echo "  # Callbacks müssen dann 127.0.0.1 zeigen"

if [[ "$APPLY" != "1" ]]; then
  echo
  echo "DRY-RUN. Settings-Datei manuell setzen oder APPLY=1 nur wenn Patch-Pfad klar."
  exit 0
fi

# Sichere Auto-Patch nur für bekannte local_settings / env-Patterns
CANDIDATES=(
  "$BACKEND/abpe_backend/local_settings.py"
  "$BACKEND/abpe_backend/settings_local.py"
  "$BACKEND/abpe_backend/settings/local.py"
  "$BACKEND/.env"
)
patched=0
for f in "${CANDIDATES[@]}"; do
  [[ -f "$f" ]] || continue
  if grep -qE 'SCHEDULER_API_BASE_URL|localhost:8000' "$f" 2>/dev/null; then
    cp -a "$f" "${f}.bak-schedurl-$TS"
    # localhost:8000 → 127.0.0.1:8000 in scheduler-relevanten Zeilen
    sed -i \
      -e "s|http://localhost:8000/scheduler/api|http://127.0.0.1:8000/scheduler/api|g" \
      -e "s|http://localhost:8000/shaduler/api|http://127.0.0.1:8000/shaduler/api|g" \
      "$f"
    echo "OK patched $f (backup ${f}.bak-schedurl-$TS)"
    patched=1
  fi
done

if [[ "$patched" -eq 0 ]]; then
  echo "Keine bekannte local_settings mit localhost gefunden — manuell setzen."
  exit 2
fi

cd "$BACKEND"
/opt/abpe/venv311/bin/python manage.py register_scheduler_jobs
echo "OK — Jobs neu registriert (Callbacks prüfen auf 127.0.0.1)"
