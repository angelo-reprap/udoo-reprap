#!/usr/bin/env bash
# Startet den AAA-Overnight-Lauf DETACHED auf dem Server
# (überlebt PuTTY/SSH-Disconnect / Windows-Standby).
#
# Auf ucs5 — kurz einloggen, starten, Fenster kann zu:
#
#   cd /mnt/public/udoo-reprap && git pull origin cursor/cv-extractor-7f07
#   bash scripts/SAFE-cv-extractor-edit.sh deploy
#
#   # Nachtlauf Celery (Import queued, Worker bleiben auf Server):
#   bash scripts/aaa-overnight-detach.sh --force
#
#   # Oder komplett sync auf Server (lang, aber unabhängig von PuTTY):
#   bash scripts/aaa-overnight-detach.sh --force --sync
#
#   # Status:
#   bash scripts/aaa-overnight-detach.sh --status
#   tail -f /tmp/aaa-overnight-latest.log
#
#   # Morgens Compare + Git-Push (auch detached ok):
#   bash scripts/aaa-overnight-detach.sh --compare-only
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
SCRIPT="$REPO/scripts/aaa-overnight-batch.sh"
PIDFILE="${PIDFILE:-/tmp/aaa-overnight.pid}"
LOG="${LOG:-/tmp/aaa-overnight-latest.log}"
STAMP_LOG="/tmp/aaa-overnight-$(date +%Y%m%d-%H%M%S).log"

cd "$REPO"

if [[ "${1:-}" == "--status" ]]; then
  if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "RUNNING pid=$(cat "$PIDFILE") log=$LOG"
    tail -n 30 "$LOG" 2>/dev/null || true
  else
    echo "NOT RUNNING (pidfile=$PIDFILE)"
    [[ -f "$LOG" ]] && { echo "--- last log ---"; tail -n 40 "$LOG"; }
  fi
  exit 0
fi

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "Schon aktiv: pid=$(cat "$PIDFILE") — $LOG" >&2
  exit 1
fi

# LOG für Batch setzen; Batch schreibt selbst mit tee — hier redirect als Backup
ln -sfn "$STAMP_LOG" "$LOG"
export LOG="$STAMP_LOG"

# nohup + disown: SIGHUP von SSH/PuTTY killt den Job nicht
nohup bash "$SCRIPT" "$@" >>"$STAMP_LOG" 2>&1 &
echo $! >"$PIDFILE"
disown || true

echo "Detached gestartet."
echo "  pid:  $(cat "$PIDFILE")"
echo "  log:  $STAMP_LOG"
echo "  link: $LOG"
echo
echo "PuTTY darf jetzt zu / Standby — Job läuft auf ucs5 weiter."
echo "Status:  bash $REPO/scripts/aaa-overnight-detach.sh --status"
echo "Follow:  tail -f $LOG"
