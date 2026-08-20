#!/usr/bin/env bash
# Detached Start für BATCH-gulp-to-aid-pipeline.sh (überlebt PuTTY/Standby).
#
# 10er-Test:
#   LIMIT=10 bash scripts/BATCH-gulp-to-aid-detach.sh
#
# Overnight alle NEED:
#   LIMIT=0 MEM_THRESH=85 CPU_THRESH=85 THROTTLE_SLEEP=45 \
#     bash scripts/BATCH-gulp-to-aid-detach.sh
#
# Status:
#   bash scripts/BATCH-gulp-to-aid-detach.sh --status
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
SCRIPT="$REPO/scripts/BATCH-gulp-to-aid-pipeline.sh"
PIDFILE="${PIDFILE:-/tmp/gulp-aid-batch.pid}"
LOG="${LOG:-/tmp/gulp-aid-batch-latest.log}"
STAMP_LOG="/tmp/gulp-aid-batch-$(date +%Y%m%d-%H%M%S).log"

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

if [[ "${1:-}" == "--stop" ]]; then
  if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    kill "$(cat "$PIDFILE")" && echo "Stopped pid=$(cat "$PIDFILE")"
  else
    echo "Not running"
  fi
  exit 0
fi

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "Schon aktiv: pid=$(cat "$PIDFILE") — $LOG" >&2
  exit 1
fi

ln -sfn "$STAMP_LOG" "$LOG"
# Args/Env durchreichen (LIMIT=10 etc. bereits in Umgebung)
nohup env LIMIT="${LIMIT:-10}" EXECUTE="${EXECUTE:-1}" \
  MEM_THRESH="${MEM_THRESH:-88}" CPU_THRESH="${CPU_THRESH:-88}" \
  SWAP_THRESH="${SWAP_THRESH:-95}" SWAP_MEM_COMBO="${SWAP_MEM_COMBO:-75}" \
  MIN_AVAIL_MB="${MIN_AVAIL_MB:-1536}" \
  THROTTLE_SLEEP="${THROTTLE_SLEEP:-30}" RUN_INVENTORY="${RUN_INVENTORY:-0}" \
  NEED="${NEED:-}" \
  bash "$SCRIPT" >>"$STAMP_LOG" 2>&1 &
echo $! >"$PIDFILE"
disown || true

echo "Detached gestartet."
echo "  pid:  $(cat "$PIDFILE")"
echo "  log:  $STAMP_LOG"
echo "  link: $LOG"
echo
echo "Status: bash $REPO/scripts/BATCH-gulp-to-aid-detach.sh --status"
echo "Follow: tail -f $LOG"
echo "Stop:   bash $REPO/scripts/BATCH-gulp-to-aid-detach.sh --stop"
