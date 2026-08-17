#!/usr/bin/env bash
# Detached Letter-Batch (überlebt PuTTY-Disconnect).
#
#   LETTER=bbb LIMIT=3 bash scripts/batch-aid-letter-detach.sh   # Smoke
#   LETTER=bbb bash scripts/batch-aid-letter-detach.sh           # alle
#   LETTER=bbb bash scripts/batch-aid-letter-detach.sh --status
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
LETTER="${LETTER:-bbb}"
LETTER="$(echo "$LETTER" | tr '[:upper:]' '[:lower:]')"
SCRIPT="$REPO/scripts/batch-aid-letter.sh"
PIDFILE="${PIDFILE:-/tmp/aid-${LETTER}-batch.pid}"
LOG="${LOG:-/tmp/aid-${LETTER}-batch-latest.log}"
STAMP_LOG="/tmp/aid-${LETTER}-batch-$(date +%Y%m%d-%H%M%S).log"

cd "$REPO"

if [[ "${1:-}" == "--status" ]]; then
  if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "RUNNING pid=$(cat "$PIDFILE") log=$LOG"
    tail -n 40 "$LOG" 2>/dev/null || true
  else
    echo "NOT RUNNING (pidfile=$PIDFILE)"
    [[ -f "$LOG" ]] && { echo "--- last log ---"; tail -n 50 "$LOG"; }
  fi
  exit 0
fi

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "Schon aktiv: pid=$(cat "$PIDFILE") — $LOG" >&2
  exit 1
fi

ln -sfn "$STAMP_LOG" "$LOG"
export LETTER LIMIT DRY_RUN IMPORT_ONLY COMPARE_ONLY SKIP_EXISTING_NEU OUT MANIFEST
export LETTER LIMIT="${LIMIT:-}" 

nohup env LETTER="$LETTER" LIMIT="${LIMIT:-0}" \
  DRY_RUN="${DRY_RUN:-0}" IMPORT_ONLY="${IMPORT_ONLY:-0}" \
  COMPARE_ONLY="${COMPARE_ONLY:-0}" SKIP_EXISTING_NEU="${SKIP_EXISTING_NEU:-0}" \
  bash "$SCRIPT" >>"$STAMP_LOG" 2>&1 &
echo $! >"$PIDFILE"
disown || true

echo "Detached gestartet (LETTER=$LETTER LIMIT=${LIMIT:-0})."
echo "  pid:  $(cat "$PIDFILE")"
echo "  log:  $STAMP_LOG"
echo "  link: $LOG"
echo
echo "Status:  LETTER=$LETTER bash $REPO/scripts/batch-aid-letter-detach.sh --status"
echo "Follow:  tail -f $LOG"
