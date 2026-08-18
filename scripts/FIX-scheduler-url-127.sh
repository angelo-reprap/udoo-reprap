#!/usr/bin/env bash
# Live: SCHEDULER URLs localhost → 127.0.0.1 (IPv6/Timeout-Falle).
# Default = Dry-Run (Ort finden). APPLY=1 patched bekannte Dateien oder
# legt Override an, wenn FORCE_OVERRIDE=1.
#
#   bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/FIX-scheduler-url-127.sh)
#   APPLY=1 bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/FIX-scheduler-url-127.sh)
#   APPLY=1 FORCE_OVERRIDE=1 bash <(git show …/FIX-scheduler-url-127.sh)
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"
APPLY="${APPLY:-0}"
FORCE_OVERRIDE="${FORCE_OVERRIDE:-0}"
TS=$(date +%Y%m%d-%H%M%S)
CLIENT="$BACKEND/abpe_shaduler/incoming/scheduler_client.py"

echo "======== FIX scheduler URL localhost→127.0.0.1 APPLY=$APPLY FORCE_OVERRIDE=$FORCE_OVERRIDE ========"

echo "=== A) Django: effektive Werte + Herkunft ==="
cd "$BACKEND"
"$PYBIN" - <<'PY'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from django.conf import settings

def show(name):
    if hasattr(settings, name):
        print(f'  {name} = {getattr(settings, name)!r}  (in settings gesetzt)')
    else:
        print(f'  {name} = (nicht gesetzt → Code-Default in scheduler_client)')

show('SCHEDULER_API_BASE_URL')
show('SHADULER_CALLBACK_BASE_URL')
print('  DJANGO_SETTINGS_MODULE =', os.environ.get('DJANGO_SETTINGS_MODULE'))
print('  settings module file   =', getattr(settings, 'SETTINGS_MODULE', None), getattr(django.conf, 'settings', None))
try:
    import abpe_backend.settings as smod
    print('  abpe_backend.settings  =', getattr(smod, '__file__', '?'))
except Exception as e:
    print('  abpe_backend.settings  ERR', e)
for k in ('SCHEDULER_API_BASE_URL', 'SHADULER_CALLBACK_BASE_URL'):
    if k in os.environ:
        print(f'  ENV {k}={os.environ[k]!r}')
PY

echo
echo "=== B) Datei-Treffer (rg/grep) ==="
search() {
  local pat="$1"
  if command -v rg >/dev/null 2>&1; then
    rg -n "$pat" "$BACKEND" --glob '*.py' --glob '*.env' --glob '*.json' \
      -g '!**/__pycache__/**' -g '!**/migrations/**' 2>/dev/null | head -40 || true
  else
    grep -rnE "$pat" "$BACKEND" --include='*.py' --include='*.env' --include='*.json' \
      2>/dev/null | grep -v __pycache__ | grep -v migrations | head -40 || true
  fi
}
search 'SCHEDULER_API_BASE_URL|SHADULER_CALLBACK_BASE_URL'
echo "--- localhost:8000 in settings-ähnlichen Dateien ---"
search 'localhost:8000'

echo
echo "=== C) scheduler_client.py Defaults ==="
if [[ -f "$CLIENT" ]]; then
  grep -n 'localhost\|127.0.0.1\|_base_url\|_callback\|_normalize' "$CLIENT" | head -30 || true
else
  echo "FEHLT: $CLIENT"
fi

echo
echo "Empfohlen:"
echo "  1) Client-Normalisierung deployen (Repo scheduler_client.py) — robust"
echo "  2) oder Settings manuell / FORCE_OVERRIDE=1"
echo "  SCHEDULER_API_BASE_URL = 'http://127.0.0.1:8000/scheduler/api'"
echo "  SHADULER_CALLBACK_BASE_URL = 'http://127.0.0.1:8000/shaduler/api'"
echo "Danach: register_scheduler_jobs — Callbacks müssen 127.0.0.1 zeigen"

if [[ "$APPLY" != "1" ]]; then
  echo
  echo "DRY-RUN. APPLY=1: patch bekannte Dateien + Client-Defaults."
  echo "APPLY=1 FORCE_OVERRIDE=1: zusätzlich local_settings.py anlegen/ergänzen."
  exit 0
fi

patched=0

# 1) Client: Defaults + ggf. alte localhost-Strings
if [[ -f "$CLIENT" ]]; then
  cp -a "$CLIENT" "${CLIENT}.bak-schedurl-$TS"
  if grep -q '_normalize_loopback' "$CLIENT" 2>/dev/null; then
    echo "OK client already has _normalize_loopback"
  else
    # Fallback: nur String-Replace der Defaults (wenn noch altes File)
    sed -i \
      -e "s|http://localhost:8000/scheduler/api|http://127.0.0.1:8000/scheduler/api|g" \
      -e "s|http://localhost:8000/shaduler/api|http://127.0.0.1:8000/shaduler/api|g" \
      "$CLIENT"
    echo "OK patched defaults in $CLIENT (backup ${CLIENT}.bak-schedurl-$TS)"
    patched=1
  fi
fi

# 2) bekannte local_settings / env
CANDIDATES=(
  "$BACKEND/abpe_backend/local_settings.py"
  "$BACKEND/abpe_backend/settings_local.py"
  "$BACKEND/abpe_backend/settings/local.py"
  "$BACKEND/.env"
)
for f in "${CANDIDATES[@]}"; do
  [[ -f "$f" ]] || continue
  if grep -qE 'SCHEDULER_API_BASE_URL|localhost:8000' "$f" 2>/dev/null; then
    cp -a "$f" "${f}.bak-schedurl-$TS"
    sed -i \
      -e "s|http://localhost:8000/scheduler/api|http://127.0.0.1:8000/scheduler/api|g" \
      -e "s|http://localhost:8000/shaduler/api|http://127.0.0.1:8000/shaduler/api|g" \
      "$f"
    echo "OK patched $f"
    patched=1
  fi
done

# 3) Override-Datei (nur mit FORCE)
OVERRIDE="$BACKEND/abpe_backend/local_settings.py"
if [[ "$FORCE_OVERRIDE" == "1" ]]; then
  if [[ ! -f "$OVERRIDE" ]]; then
    cat > "$OVERRIDE" <<'EOF'
# Auto: loopback-fix (FIX-scheduler-url-127) — localhost→127.0.0.1
SCHEDULER_API_BASE_URL = 'http://127.0.0.1:8000/scheduler/api'
SHADULER_CALLBACK_BASE_URL = 'http://127.0.0.1:8000/shaduler/api'
EOF
    echo "OK created $OVERRIDE"
    patched=1
  elif ! grep -q 'SCHEDULER_API_BASE_URL' "$OVERRIDE"; then
    cp -a "$OVERRIDE" "${OVERRIDE}.bak-schedurl-$TS"
    cat >> "$OVERRIDE" <<'EOF'

# Auto: loopback-fix (FIX-scheduler-url-127)
SCHEDULER_API_BASE_URL = 'http://127.0.0.1:8000/scheduler/api'
SHADULER_CALLBACK_BASE_URL = 'http://127.0.0.1:8000/shaduler/api'
EOF
    echo "OK appended to $OVERRIDE"
    patched=1
  else
    echo "Override existiert schon mit SCHEDULER_API_BASE_URL — manuell prüfen: $OVERRIDE"
  fi
  # Hinweis: wirkt nur wenn settings.py local_settings importiert
  if ! grep -rqE 'local_settings' "$BACKEND/abpe_backend" --include='*.py' 2>/dev/null; then
    echo "WARN: kein Import von local_settings in abpe_backend gefunden."
    echo "      Dann reicht Client-Normalisierung (Repo) oder Settings-Datei finden."
  fi
fi

if [[ "$patched" -eq 0 ]]; then
  echo "Nichts gepatcht. Optionen:"
  echo "  a) Repo-File scheduler_client.py (mit _normalize_loopback) auf Live kopieren"
  echo "  b) APPLY=1 FORCE_OVERRIDE=1 …"
  echo "  c) Settings-Datei manuell (Abschnitt A/B oben)"
  exit 2
fi

echo
echo "=== register_scheduler_jobs ==="
"$PYBIN" manage.py register_scheduler_jobs
echo "OK — Callbacks müssen http://127.0.0.1:8000/shaduler/... zeigen"
