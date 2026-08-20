#!/usr/bin/env bash
# SAFE: Gulp-Keywords v1.3 → main_labeler (+ neue section_label_keywords.py)
#
# Auf ucs5 — Reihenfolge strikt:
#   1) bash scripts/SAFE-gulp-keywords.sh prepare
#        → backup_restore -save
#        → Live-Kopien nach Repo (artifacts/.../from-ucs5-*) UND nach Repo_abpe/...
#          (nur wenn Live neuer/anders; main_labeler wird NICHT stumm mit Agent-Diff überschrieben
#           ohne dass du prepare bewusst laufen lässt)
#   2) Diff ansehen:  git diff Repo_abpe/cv_extractor/incoming/services/main_labeler.py
#   3) bash scripts/SAFE-gulp-keywords.sh deploy
#        → nochmal -save, dann Repo → Live
#   4) bash scripts/RUN-bbb-bueckling-pipeline.sh
#
# Recover:
#   bash scripts/SAFE-gulp-keywords.sh restore
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/gulp-keyword-pipeline-1532}"
LIVE_CV="${LIVE_CV:-/opt/abpe/backend/apps/cv_extractor}"
SRC="$REPO/Repo_abpe/cv_extractor/incoming"
BACKEND="${BACKEND:-/opt/abpe/backend}"
BR="${BR:-python3 Archiv/backup_restore.py}"
MSG_PREFIX="${MSG_PREFIX:-gulp keywords v1.3}"

FILES=(
  services/main_labeler.py
  services/section_label_keywords.py
)

cmd="${1:-help}"

_save_all() {
  cd "$BACKEND"
  for rel in "${FILES[@]}"; do
    live="apps/cv_extractor/$rel"
    if [[ ! -f "$live" ]]; then
      echo "SKIP -save (fehlt Live): $live"
      continue
    fi
    echo ">>> -save $live"
    $BR -save "$live" -m "$MSG_PREFIX $(date +%Y%m%d-%H%M%S)"
  done
}

_prepare() {
  local ts snap
  ts=$(date +%Y%m%d-%H%M%S)
  snap="$REPO/artifacts/gulp-keyword/live-baselines/from-ucs5-$ts"
  mkdir -p "$snap" "$SRC/services"

  cd "$REPO"
  git fetch origin "$BRANCH" 2>/dev/null || true
  if git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
    git checkout "$BRANCH"
    git pull origin "$BRANCH" 2>/dev/null || true
  elif git rev-parse --verify "origin/$BRANCH" >/dev/null 2>&1; then
    git checkout -B "$BRANCH" "origin/$BRANCH"
  else
    echo "WARN: Branch $BRANCH fehlt lokal/remote — bleibe auf $(git branch --show-current)"
  fi

  echo "=== 1) backup_restore -save ==="
  _save_all

  echo "=== 2) Live → Snapshot + Repo (nur vorhandene Live-Dateien) ==="
  for rel in "${FILES[@]}"; do
    src="$LIVE_CV/$rel"
    if [[ ! -f "$src" ]]; then
      echo "SKIP pull (fehlt Live, wird bei deploy neu angelegt): $src"
      continue
    fi
    mkdir -p "$snap/$(dirname "$rel")"
    cp -a "$src" "$snap/$rel"
    # Live-Stand zusätzlich als .live-copy neben Repo-Datei legen (zum Ansehen)
    cp -a "$src" "$SRC/$rel.live-copy-$ts"
    echo "OK snap+live-copy $rel → $snap/$rel"
    echo "    und $SRC/$rel.live-copy-$ts"
  done

  echo
  echo "Als Nächstes:"
  echo "  # Live-Kopie vs Agent-Stand vergleichen:"
  echo "  diff -u $SRC/services/main_labeler.py.live-copy-$ts \\"
  echo "          $SRC/services/main_labeler.py | less"
  echo "  # Wenn Agent-Stand OK → deploy"
  echo "  bash $REPO/scripts/SAFE-gulp-keywords.sh deploy"
}

_deploy() {
  cd "$REPO"
  git fetch origin "$BRANCH" 2>/dev/null || true
  git checkout "$BRANCH" 2>/dev/null || true
  git pull origin "$BRANCH" 2>/dev/null || true

  echo "=== 1) backup_restore -save (nochmal vor Überschreiben) ==="
  _save_all

  echo "=== 2) Repo → Live ==="
  for rel in "${FILES[@]}"; do
    src="$SRC/$rel"
    dst="$LIVE_CV/$rel"
    if [[ ! -f "$src" ]]; then
      echo "FAIL: fehlt Repo: $src" >&2
      exit 1
    fi
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst"
    echo "OK deploy $rel"
  done

  echo
  echo "Smoke:"
  echo "  cd $BACKEND && python3 -c \"from apps.cv_extractor.services.main_labeler import FIRST_WORD_TO_LABEL; print('stammdaten' in FIRST_WORD_TO_LABEL, 'projekte' in FIRST_WORD_TO_LABEL)\""
  echo "  bash $REPO/scripts/RUN-bbb-bueckling-pipeline.sh"
}

_restore() {
  cd "$BACKEND"
  for rel in "${FILES[@]}"; do
    live="apps/cv_extractor/$rel"
    if [[ ! -f "$live" ]]; then
      echo "SKIP restore: $live"
      continue
    fi
    echo ">>> -restore $live"
    $BR -restore "$live" || echo "WARN: restore fehlgeschlagen für $live"
  done
}

case "$cmd" in
  prepare) _prepare ;;
  deploy)  _deploy ;;
  restore) _restore ;;
  save)    _save_all ;;
  help|*)
    sed -n '2,20p' "$0"
    echo "Usage: $0 {prepare|deploy|restore|save}"
    exit 0
    ;;
esac
