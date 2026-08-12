#!/usr/bin/env bash
# Overnight-Batch: alle neuesten AID-PDFs unter AID_profile/aaa → Pipeline → neu/cv
# Danach Repro-Vergleich Original vs neu/cv → artifacts/aaa-repro (für Git-Sync)
#
# WICHTIG (Windows/PuTTY): Nicht im Vordergrund lassen — Standby trennt SSH.
# Immer detached starten:
#   bash scripts/aaa-overnight-detach.sh --force
#   bash scripts/aaa-overnight-detach.sh --status
#   bash scripts/aaa-overnight-detach.sh --compare-only
#
# Direkt (nur in tmux/screen oder nach detach):
#   bash scripts/aaa-overnight-batch.sh --force
#   bash scripts/aaa-overnight-batch.sh --sync --limit 3 --force
#   bash scripts/aaa-overnight-batch.sh --compare-only
#   bash scripts/aaa-overnight-batch.sh --force --wait-neu   # async + warten + compare
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
LETTER="${LETTER:-aaa}"
BRANCH="${BRANCH:-cursor/cv-extractor-7f07}"
OUT="${OUT:-$REPO/artifacts/${LETTER}-repro}"
LOG="${LOG:-/tmp/${LETTER}-overnight-$(date +%Y%m%d-%H%M%S).log}"
AID_ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"

DRY=0
FORCE=0
SYNC=0
COMPARE_ONLY=0
WAIT_NEU=0
LIMIT=0
WAIT_MAX_MIN="${WAIT_MAX_MIN:-480}"   # max. 8h auf neu/cv warten
WAIT_STABLE_ROUNDS="${WAIT_STABLE_ROUNDS:-3}"  # 3× gleiche Anzahl = fertig

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --force) FORCE=1; shift ;;
    --sync) SYNC=1; shift ;;
    --compare-only) COMPARE_ONLY=1; shift ;;
    --wait-neu) WAIT_NEU=1; shift ;;
    --limit) LIMIT="${2:-0}"; shift 2 ;;
    --letter) LETTER="${2:-aaa}"; OUT="$REPO/artifacts/${LETTER}-repro"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

mkdir -p "$(dirname "$LOG")"
# Append-Log (kein Process-Substitution — robuster unter nohup)
exec >>"$LOG" 2>&1

echo "======== AAA Overnight Batch ========"
echo "REPO=$REPO BACKEND=$BACKEND LETTER=$LETTER"
echo "OUT=$OUT LOG=$LOG"
echo "DRY=$DRY FORCE=$FORCE SYNC=$SYNC COMPARE_ONLY=$COMPARE_ONLY WAIT_NEU=$WAIT_NEU LIMIT=$LIMIT"
echo "Start: $(date -Iseconds)"
echo "Host: $(hostname) pid=$$"
echo

cd "$REPO"
git fetch origin "$BRANCH" || true
git checkout "$BRANCH" || true
git pull origin "$BRANCH" || true

_count_neu_pdf() {
  find "$AID_ROOT/$LETTER" -path '*/neu/cv/AID-*.pdf' 2>/dev/null | wc -l | tr -d ' '
}

if [[ "$COMPARE_ONLY" -eq 0 ]]; then
  echo ">>> Deploy SAFE files (falls nötig)"
  bash "$REPO/scripts/SAFE-cv-extractor-edit.sh" deploy || {
    echo "WARN: SAFE deploy fehlgeschlagen — fahre mit Live-Code fort"
  }

  cd "$BACKEND"
  # shellcheck disable=SC1091
  [[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
  [[ -f venv311/bin/activate ]] && source venv311/bin/activate

  ARGS=(import_aid_profiles --letter "$LETTER")
  [[ "$DRY" -eq 1 ]] && ARGS+=(--dry-run)
  [[ "$FORCE" -eq 1 ]] && ARGS+=(--no-skip-existing)
  [[ "$SYNC" -eq 1 ]] && ARGS+=(--sync)
  [[ "$LIMIT" -gt 0 ]] && ARGS+=(--limit "$LIMIT")

  echo ">>> python3 manage.py ${ARGS[*]}"
  python3 manage.py "${ARGS[@]}"

  if [[ "$SYNC" -eq 0 && "$DRY" -eq 0 ]]; then
    echo
    echo "Import gequeued (Celery auf Server). PuTTY-Disconnect ist egal."
    echo "neu/cv Count jetzt: $(_count_neu_pdf)"
    if [[ "$WAIT_NEU" -eq 1 ]]; then
      echo ">>> Warte auf stabile neu/cv Anzahl (max ${WAIT_MAX_MIN} min)…"
      prev=-1
      stable=0
      for ((i=0; i<WAIT_MAX_MIN; i+=2)); do
        cur="$(_count_neu_pdf)"
        echo "$(date -Iseconds) neu/cv AID-PDFs=$cur (stable=$stable/$WAIT_STABLE_ROUNDS)"
        if [[ "$cur" -eq "$prev" && "$cur" -gt 0 ]]; then
          stable=$((stable + 1))
          if [[ "$stable" -ge "$WAIT_STABLE_ROUNDS" ]]; then
            echo "Stabil — Compare starten."
            COMPARE_ONLY=1
            break
          fi
        else
          stable=0
        fi
        prev=$cur
        sleep 120
      done
      if [[ "$COMPARE_ONLY" -ne 1 ]]; then
        echo "WARN: Timeout beim Warten — Compare trotzdem versuchen."
        COMPARE_ONLY=1
      fi
    else
      echo "Morgens oder später:"
      echo "  bash $REPO/scripts/aaa-overnight-detach.sh --compare-only"
    fi
  fi
fi

if [[ "$DRY" -eq 1 ]]; then
  echo "Dry-run: kein Compare."
  echo "Ende: $(date -Iseconds)"
  exit 0
fi

# Compare nach sync, compare-only, oder wait-neu
if [[ "$COMPARE_ONLY" -eq 1 || "$SYNC" -eq 1 ]]; then
  cd "$BACKEND"
  # shellcheck disable=SC1091
  [[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
  [[ -f venv311/bin/activate ]] && source venv311/bin/activate

  mkdir -p "$OUT"
  echo ">>> compare_aid_neu_cv → $OUT"
  python3 manage.py compare_aid_neu_cv --letter "$LETTER" --out "$OUT"

  echo
  echo ">>> Git-Sync der Artifacts (Cloud-Agent kann dann lesen)"
  cd "$REPO"
  git add "artifacts/${LETTER}-repro" || true
  if git diff --cached --quiet; then
    echo "Keine neuen Artifact-Änderungen."
  else
    git commit -m "chore: ${LETTER} repro original vs neu/cv $(date +%Y-%m-%d)" || true
    git push -u origin "$BRANCH" || {
      echo "WARN: git push fehlgeschlagen — bitte manuell pushen"
    }
  fi
fi

echo
echo "Ende: $(date -Iseconds)"
echo "Log: $LOG"
