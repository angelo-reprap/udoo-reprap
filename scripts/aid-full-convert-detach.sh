#!/usr/bin/env bash
# Startet AID Full Convert DETACHED (überlebt PuTTY/SSH-Disconnect / Windows-Standby).
#
# Auf ucs5 — kurz einloggen, starten, Fenster darf zu:
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/aid-publish-xml-sanitize-1532
#   git checkout origin/cursor/aid-publish-xml-sanitize-1532 -- \
#     scripts/aid-full-convert.sh scripts/aid-full-convert-detach.sh \
#     scripts/deploy-aid-publish-xml-fix.sh scripts/batch-aid-letter.sh
#
#   # Smoke 2 Profile:
#   LIMIT=2 LETTERS=bbb bash scripts/aid-full-convert-detach.sh
#
#   # Alles (Resume, Disk-Guard, Rework-Liste):
#   bash scripts/aid-full-convert-detach.sh
#
#   # Status / Stop / Follow:
#   bash scripts/aid-full-convert-detach.sh --status
#   bash scripts/aid-full-convert-detach.sh --stop
#   tail -f /tmp/aid-full-convert-latest.log
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
SCRIPT="$REPO/scripts/aid-full-convert.sh"
PIDFILE="${PIDFILE:-/tmp/aid-full-convert.pid}"
LOG_LINK="${LOG_LINK:-/tmp/aid-full-convert-latest.log}"
STATE_DIR="${STATE_DIR:-$REPO/artifacts/aid-full-convert-state}"
STAMP_LOG="/tmp/aid-full-convert-$(date +%Y%m%d-%H%M%S).log"

cd "$REPO"

case "${1:-}" in
  --status)
    echo "=== AID Full Convert Status ==="
    if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "RUNNING pid=$(cat "$PIDFILE")"
    else
      echo "NOT RUNNING (pidfile=$PIDFILE)"
    fi
    if [[ -f "$STATE_DIR/latest.env" ]]; then
      echo "--- latest.env ---"
      cat "$STATE_DIR/latest.env"
    fi
    if [[ -f "$STATE_DIR/latest/progress.txt" ]]; then
      echo "--- progress ---"
      cat "$STATE_DIR/latest/progress.txt"
    fi
    if [[ -f "$STATE_DIR/latest/summary.txt" ]]; then
      echo "--- summary ---"
      cat "$STATE_DIR/latest/summary.txt"
    fi
    echo "--- log tail ($LOG_LINK) ---"
    tail -n 40 "$LOG_LINK" 2>/dev/null || true
    if [[ -f "$STATE_DIR/latest/rework-summary.txt" ]]; then
      echo "--- rework ---"
      head -n 40 "$STATE_DIR/latest/rework-summary.txt"
    fi
    # quick disk
    ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"
    echo "--- disk ---"
    df -h "$ROOT" "$REPO" 2>/dev/null | sed 's/^/  /' || true
    exit 0
    ;;
  --stop)
    if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      pid="$(cat "$PIDFILE")"
      echo "Stopping pid=$pid …"
      kill "$pid" 2>/dev/null || true
      sleep 2
      kill -9 "$pid" 2>/dev/null || true
      rm -f "$PIDFILE"
      echo "Stopped."
    else
      echo "Nicht aktiv."
      rm -f "$PIDFILE"
    fi
    exit 0
    ;;
esac

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "Schon aktiv: pid=$(cat "$PIDFILE") — $LOG_LINK" >&2
  echo "Status: bash $0 --status" >&2
  exit 1
fi

if [[ ! -f "$SCRIPT" ]]; then
  echo "ERROR: $SCRIPT fehlt. Branch pull/checkout der Scripts zuerst." >&2
  exit 1
fi
chmod +x "$SCRIPT" "$REPO/scripts/deploy-aid-publish-xml-fix.sh" 2>/dev/null || true

ln -sfn "$STAMP_LOG" "$LOG_LINK"
mkdir -p "$STATE_DIR"

# nohup + disown: SIGHUP von SSH/PuTTY killt den Job nicht
# shellcheck disable=SC2086
nohup env \
  LETTERS="${LETTERS:-}" \
  LIMIT="${LIMIT:-0}" \
  SKIP_EXISTING_NEU="${SKIP_EXISTING_NEU:-1}" \
  SKIP_DIRS="${SKIP_DIRS:-}" \
  MIN_FREE_GB="${MIN_FREE_GB:-15}" \
  MIN_FREE_GB_REPO="${MIN_FREE_GB_REPO:-5}" \
  WAVE="${WAVE:-25}" \
  WAVE_SLEEP_SEC="${WAVE_SLEEP_SEC:-30}" \
  COMPARE="${COMPARE:-0}" \
  COMPARE_MIN_SCORE="${COMPARE_MIN_SCORE:-80}" \
  DRY_RUN="${DRY_RUN:-0}" \
  DEPLOY_FIX="${DEPLOY_FIX:-1}" \
  STATE_DIR="$STATE_DIR" \
  LOG="$STAMP_LOG" \
  bash "$SCRIPT" >>"$STAMP_LOG" 2>&1 &
echo $! >"$PIDFILE"
disown || true

echo "Detached gestartet."
echo "  pid:    $(cat "$PIDFILE")"
echo "  log:    $STAMP_LOG"
echo "  link:   $LOG_LINK"
echo "  state:  $STATE_DIR/latest"
echo
echo "PuTTY darf zu / Standby — Job läuft auf dem Server weiter."
echo "Status:  bash $REPO/scripts/aid-full-convert-detach.sh --status"
echo "Follow:  tail -f $LOG_LINK"
echo "Stop:    bash $REPO/scripts/aid-full-convert-detach.sh --stop"
echo
echo "Smoke:   LIMIT=2 LETTERS=bbb bash $REPO/scripts/aid-full-convert-detach.sh"
echo "Voll:    LETTERS=  (leer=alle) LIMIT=0 bash …"
