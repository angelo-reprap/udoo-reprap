#!/usr/bin/env bash
# Stellt sicher: abpe-scheduler-loop laeuft STABIL (autostart + autorestart + RUNNING).
# Ohne diesen Prozess: kein email_index / keine MeetMe-Reminder-Periodik.
#
# Usage (ucs5):
#   bash <(git -C /mnt/public/udoo-reprap show origin/cursor/posteingang-index-3min-7f07:scripts/ENSURE-abpe-scheduler-loop.sh)
#   # oder lokal im Repo-Checkout:
#   bash scripts/ENSURE-abpe-scheduler-loop.sh
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-origin/cursor/posteingang-index-3min-7f07}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"
LIVE_CMD="${LIVE_CMD:-/opt/abpe/backend/apps/abpe_scheduler/management/commands}"
CONF_DIR="${CONF_DIR:-/etc/supervisor/conf.d}"

echo "======== ENSURE abpe-scheduler-loop $(date -Iseconds) ========"

# --- 1) scheduler_loop.py aus Branch nach Live ---
if [[ -d "$REPO/.git" ]]; then
  cd "$REPO"
  git fetch origin "${BRANCH#origin/}" 2>/dev/null || git fetch origin || true
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

if [[ -d "$REPO/.git" ]]; then
  git -C "$REPO" archive "$BRANCH" \
    Repo_abpe/abpe_scheduler/incoming/management/commands/scheduler_loop.py \
    2>/dev/null | tar -x -C "$TMP" || true
fi

SRC="$TMP/Repo_abpe/abpe_scheduler/incoming/management/commands/scheduler_loop.py"
# Fallback: Skript liegt schon im Checkout
if [[ ! -f "$SRC" && -f "$REPO/Repo_abpe/abpe_scheduler/incoming/management/commands/scheduler_loop.py" ]]; then
  SRC="$REPO/Repo_abpe/abpe_scheduler/incoming/management/commands/scheduler_loop.py"
fi
if [[ ! -f "$SRC" && -f "$(dirname "$0")/../Repo_abpe/abpe_scheduler/incoming/management/commands/scheduler_loop.py" ]]; then
  SRC="$(cd "$(dirname "$0")/.." && pwd)/Repo_abpe/abpe_scheduler/incoming/management/commands/scheduler_loop.py"
fi

if [[ -f "$SRC" ]]; then
  mkdir -p "$LIVE_CMD"
  if [[ -f "$LIVE_CMD/scheduler_loop.py" ]]; then
    cp -a "$LIVE_CMD/scheduler_loop.py" "$LIVE_CMD/scheduler_loop.py.bak.$(date +%Y%m%d_%H%M%S)"
  fi
  cp -a "$SRC" "$LIVE_CMD/scheduler_loop.py"
  echo "OK loop → $LIVE_CMD/scheduler_loop.py"
else
  echo "WARN: scheduler_loop.py nicht im Branch/Checkout — Live-Datei bleibt"
fi

# --- 2) Supervisor-Conf: autostart/autorestart erzwingen ---
patch_conf() {
  local f="$1"
  [[ -f "$f" ]] || return 1
  local bak="$f.bak.$(date +%Y%m%d_%H%M%S)"
  cp -a "$f" "$bak"
  # Nur im [program:abpe-scheduler-loop]-Block patchen wenn Datei mehrere Programme hat
  if grep -q '\[program:abpe-scheduler-loop\]' "$f"; then
    # Einfacher Ansatz: globale Keys fuer diese Datei setzen/ersetzen
    for key in autostart autorestart; do
      if grep -qE "^[[:space:]]*${key}[[:space:]]*=" "$f"; then
        sed -i -E "s/^[[:space:]]*${key}[[:space:]]*=.*/${key}=true/" "$f"
      else
        # nach program-Header einfuegen
        sed -i "/\[program:abpe-scheduler-loop\]/a ${key}=true" "$f"
      fi
    done
    # startretries hoch setzen falls vorhanden
    if grep -qE '^[[:space:]]*startretries[[:space:]]*=' "$f"; then
      sed -i -E 's/^[[:space:]]*startretries[[:space:]]*=.*/startretries=999/' "$f"
    fi
    echo "OK gepatcht: $f (Backup $bak)"
    return 0
  fi
  return 1
}

FOUND=0
if [[ -d "$CONF_DIR" ]]; then
  while IFS= read -r -d '' conf; do
    if grep -q 'abpe-scheduler-loop\|scheduler_loop' "$conf" 2>/dev/null; then
      if patch_conf "$conf"; then
        FOUND=1
      fi
    fi
  done < <(find "$CONF_DIR" -type f \( -name '*.conf' -o -name '*.ini' \) -print0 2>/dev/null)
fi

# Weitere uebliche Pfade
for alt in /etc/supervisord.d /opt/abpe/supervisor /etc/supervisor; do
  [[ -d "$alt" ]] || continue
  while IFS= read -r -d '' conf; do
    if grep -q '\[program:abpe-scheduler-loop\]' "$conf" 2>/dev/null; then
      if patch_conf "$conf"; then
        FOUND=1
      fi
    fi
  done < <(find "$alt" -type f \( -name '*.conf' -o -name '*.ini' \) -print0 2>/dev/null)
done

if [[ "$FOUND" -eq 0 ]]; then
  echo "WARN: keine bestehende Conf mit [program:abpe-scheduler-loop] gefunden"
  if [[ -d "$CONF_DIR" ]]; then
    # Vorlage installieren
    TEMPLATE=""
    if [[ -d "$REPO/.git" ]]; then
      git -C "$REPO" show "$BRANCH:deploy/supervisor/abpe-scheduler-loop.conf" \
        > "$TMP/abpe-scheduler-loop.conf" 2>/dev/null || true
      [[ -s "$TMP/abpe-scheduler-loop.conf" ]] && TEMPLATE="$TMP/abpe-scheduler-loop.conf"
    fi
    if [[ -z "$TEMPLATE" && -f "$REPO/deploy/supervisor/abpe-scheduler-loop.conf" ]]; then
      TEMPLATE="$REPO/deploy/supervisor/abpe-scheduler-loop.conf"
    fi
    if [[ -n "$TEMPLATE" ]]; then
      cp -a "$TEMPLATE" "$CONF_DIR/abpe-scheduler-loop.conf"
      echo "OK installiert: $CONF_DIR/abpe-scheduler-loop.conf"
      FOUND=1
    fi
  fi
fi

# --- 3) Supervisor neu laden + starten ---
if command -v supervisorctl >/dev/null 2>&1; then
  supervisorctl reread || true
  supervisorctl update || true
  # start ist idempotent wenn schon RUNNING
  supervisorctl start abpe-scheduler-loop || supervisorctl restart abpe-scheduler-loop || true
  sleep 2
  echo
  echo "=== Status ==="
  supervisorctl status abpe-django abpe-celery abpe-scheduler-loop 2>/dev/null \
    || supervisorctl status all | grep -E 'abpe-' || true

  if supervisorctl status abpe-scheduler-loop 2>/dev/null | grep -q RUNNING; then
    echo
    echo "OK abpe-scheduler-loop ist RUNNING"
    exit 0
  fi
  echo
  echo "FAIL: abpe-scheduler-loop ist NICHT RUNNING"
  echo "  → supervisorctl tail -f abpe-scheduler-loop"
  echo "  → pruefen: $PYBIN $BACKEND/manage.py scheduler_loop --interval=5"
  exit 1
else
  echo "FAIL: supervisorctl nicht gefunden"
  exit 1
fi
