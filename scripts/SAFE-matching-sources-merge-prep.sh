#!/usr/bin/env bash
# Versicherung + Live → Repo für Matching Gulp/FLM-Merge.
#
# ucs5 (PFLICHT vor Implementierungs-Deploy):
#   cd /mnt/public/udoo-reprap
#   git fetch origin && git checkout cursor/matching-shortlist-weights-1532 && git pull
#   bash scripts/SAFE-matching-sources-merge-prep.sh
#   # optional Commit der Live-Basis:
#   bash scripts/SAFE-matching-sources-merge-prep.sh --commit
#
# Macht:
#   1) Backup der Live-Dateien unter /opt/abpe/backups/matching-sources-merge-<ts>/
#   2) Live → Repo (nur die betroffenen Dateien), damit Repo = Live-Stand
#   3) Diff-Report
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
LIVE_MW="${LIVE_MW:-/opt/abpe/backend/apps/abpe_matching_workflow}"
LIVE_SH="${LIVE_SH:-/opt/abpe/backend/apps/abpe_shaduler}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/abpe/backups}"
TS=$(date +%Y%m%d-%H%M%S)
BAK="$BACKUP_ROOT/matching-sources-merge-$TS"
# Live → Repo nur mit --sync (sonst würden neuere Repo-Patches überschrieben)
SYNC_LIVE=0
DO_COMMIT=0
for a in "$@"; do
  case "$a" in
    --commit|--push) DO_COMMIT=1 ;;
    --sync|--sync-live-to-repo) SYNC_LIVE=1 ;;
  esac
done

mkdir -p "$BAK"/{matching_workflow,abpe_shaduler,abpe_ui}
echo "======== SAFE matching sources merge PREP $TS ========"
echo "Backup → $BAK"

backup_one() {
  local src="$1" dest="$2"
  if [[ -f "$src" ]]; then
    mkdir -p "$(dirname "$dest")"
    cp -a "$src" "$dest"
    echo "BAK $(basename "$src")"
  else
    echo "SKIP bak (fehlt): $src"
  fi
}

# Live → Backup
backup_one "$LIVE_MW/services/matching_engine.py" "$BAK/matching_workflow/matching_engine.py"
backup_one "$LIVE_MW/services/matching_service.py" "$BAK/matching_workflow/matching_service.py"
backup_one "$LIVE_MW/views.py" "$BAK/matching_workflow/views.py"
backup_one "$LIVE_MW/tasks.py" "$BAK/matching_workflow/tasks.py"
backup_one "$LIVE_SH/services/radar_berater_gulp.py" "$BAK/abpe_shaduler/radar_berater_gulp.py"
backup_one "$LIVE_SH/services/radar_berater_fl.py" "$BAK/abpe_shaduler/radar_berater_fl.py"
backup_one "$LIVE_UI/static/abpe_ui/js/mod/mod-matching.js" "$BAK/abpe_ui/mod-matching.js"

# Live → Repo
sync_one() {
  local src="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  if [[ ! -f "$src" ]]; then
    echo "WARN live fehlt: $src"
    return 0
  fi
  if [[ -f "$dest" ]] && cmp -s "$src" "$dest"; then
    echo "OK sync (identisch) $(basename "$dest")"
    return 0
  fi
  cp -a "$src" "$dest"
  echo "SYNC live→repo $(basename "$dest")"
}

cd "$REPO"
if [[ "$SYNC_LIVE" == "1" ]]; then
  echo "SYNC live→repo (explizit angefordert)"
  sync_one "$LIVE_MW/services/matching_engine.py" \
    "$REPO/Repo_abpe/abpe_matching_workflow/incoming/services/matching_engine.py"
  sync_one "$LIVE_MW/services/matching_service.py" \
    "$REPO/Repo_abpe/abpe_matching_workflow/incoming/services/matching_service.py"
  sync_one "$LIVE_MW/views.py" \
    "$REPO/Repo_abpe/abpe_matching_workflow/incoming/views.py"
  sync_one "$LIVE_MW/tasks.py" \
    "$REPO/Repo_abpe/abpe_matching_workflow/incoming/tasks.py"
  sync_one "$LIVE_SH/services/radar_berater_gulp.py" \
    "$REPO/Repo_abpe/abpe_shaduler/incoming/services/radar_berater_gulp.py"
  sync_one "$LIVE_SH/services/radar_berater_fl.py" \
    "$REPO/Repo_abpe/abpe_shaduler/incoming/services/radar_berater_fl.py"
  sync_one "$LIVE_UI/static/abpe_ui/js/mod/mod-matching.js" \
    "$REPO/Repo_abpe/abpe_ui/incoming/mod-matching.js"
  if [[ -f "$REPO/Repo_abpe/abpe_ui/incoming/mod-matching.js" ]]; then
    cp -a "$REPO/Repo_abpe/abpe_ui/incoming/mod-matching.js" \
      "$REPO/Repo_abpe/abpe_ui/incoming/static_abpe_ui/js/mod/mod-matching.js"
  fi
else
  echo "Kein live→repo Sync (Default). Diff-Check:"
  for pair in \
    "$LIVE_MW/services/matching_engine.py|$REPO/Repo_abpe/abpe_matching_workflow/incoming/services/matching_engine.py" \
    "$LIVE_SH/services/radar_berater_gulp.py|$REPO/Repo_abpe/abpe_shaduler/incoming/services/radar_berater_gulp.py" \
    "$LIVE_SH/services/radar_berater_fl.py|$REPO/Repo_abpe/abpe_shaduler/incoming/services/radar_berater_fl.py" \
    "$LIVE_UI/static/abpe_ui/js/mod/mod-matching.js|$REPO/Repo_abpe/abpe_ui/incoming/mod-matching.js"
  do
    IFS='|' read -r L R <<< "$pair"
    if [[ -f "$L" && -f "$R" ]]; then
      if cmp -s "$L" "$R"; then echo "  = $(basename "$R")"
      else echo "  ≠ $(basename "$R")  (Live weicht ab — Backup liegt unter $BAK)"
      fi
    fi
  done
  echo "Bei Bedarf: bash scripts/SAFE-matching-sources-merge-prep.sh --sync"
fi

echo
echo "Diff-Stat (working tree):"
git -C "$REPO" status --short Repo_abpe/abpe_matching_workflow Repo_abpe/abpe_shaduler/incoming/services/radar_berater_*.py Repo_abpe/abpe_ui/incoming/mod-matching.js || true

if [[ "$DO_COMMIT" == "1" ]]; then
  git -C "$REPO" add \
    Repo_abpe/abpe_matching_workflow/incoming/services/matching_engine.py \
    Repo_abpe/abpe_matching_workflow/incoming/services/matching_service.py \
    Repo_abpe/abpe_matching_workflow/incoming/views.py \
    Repo_abpe/abpe_matching_workflow/incoming/tasks.py \
    Repo_abpe/abpe_shaduler/incoming/services/radar_berater_gulp.py \
    Repo_abpe/abpe_shaduler/incoming/services/radar_berater_fl.py \
    Repo_abpe/abpe_ui/incoming/mod-matching.js \
    Repo_abpe/abpe_ui/incoming/static_abpe_ui/js/mod/mod-matching.js \
    2>/dev/null || true
  if git -C "$REPO" diff --cached --quiet; then
    echo "Nichts zu committen (Live=Repo)."
  else
    git -C "$REPO" commit -m "chore(matching): live→repo sync before gulp/flm merge ($TS)"
    git -C "$REPO" push -u origin HEAD || true
    echo "Commit+Push der Live-Basis erledigt."
  fi
fi

echo
echo "Backup: $BAK"
echo "Danach Cloud-Agent: git pull — dann Merge-Implementierung deployen."
echo "Restore-Beispiel: cp -a $BAK/matching_workflow/matching_engine.py $LIVE_MW/services/matching_engine.py"
