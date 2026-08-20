#!/usr/bin/env bash
# SAFE Deploy: Gulp-Inhalt (Wohnort/Jahrgang/Skills/Cleaner-Importe)
#
# Convert liest gulp_profile_clean bereits aus dem Repo.
# Import/TXT laufen über Live /opt/abpe → diese Dateien müssen deployed werden.
#
#   cd /mnt/public/udoo-reprap && git pull origin cursor/gulp-keyword-pipeline-1532
#   bash scripts/SAFE-gulp-content-deploy.sh prepare   # -save + optional Live→Repo nur bei Drift
#   bash scripts/SAFE-gulp-content-deploy.sh deploy    # Repo → Live
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/gulp-keyword-pipeline-1532}"
LIVE_CV="${LIVE_CV:-/opt/abpe/backend/apps/cv_extractor}"
SRC="$REPO/Repo_abpe/cv_extractor/incoming"
BACKEND="${BACKEND:-/opt/abpe/backend}"
BR="${BR:-python3 Archiv/backup_restore.py}"
MSG_PREFIX="${MSG_PREFIX:-gulp content Wohnort/Skills}"

FILES=(
  extractors/aid_regex_extractor.py
  services/main_db_importer.py
  services/url_fl_db_importer.py
  management/commands/cleanup_aid_test_imports.py
)

cmd="${1:-help}"

_save_all() {
  cd "$BACKEND"
  for rel in "${FILES[@]}"; do
    live="apps/cv_extractor/$rel"
    if [[ ! -f "$live" ]]; then
      echo "SKIP (fehlt Live): $live"
      continue
    fi
    echo ">>> -save $live"
    $BR -save "$live" -m "$MSG_PREFIX vor Deploy $(date +%Y%m%d-%H%M%S)"
  done
}

_deploy() {
  for rel in "${FILES[@]}"; do
    src="$SRC/$rel"
    dst="$LIVE_CV/$rel"
    [[ -f "$src" ]] || { echo "FAIL fehlt Repo: $src" >&2; exit 1; }
    mkdir -p "$(dirname "$dst")"
    echo ">>> cp $rel → Live"
    cp -a "$src" "$dst"
  done
  echo "OK deployed ${#FILES[@]} Dateien → $LIVE_CV"
  echo "Hinweis: gulp_profile_clean.py bleibt Repo-only (CONVERT lädt es von dort)."
}

case "$cmd" in
  prepare)
    cd "$REPO"
    git fetch origin "$BRANCH"
    git checkout "$BRANCH"
    git pull --ff-only origin "$BRANCH" || true
    _save_all
    echo "prepare OK — als Nächstes: bash $0 deploy"
    ;;
  deploy)
    cd "$REPO"
    git pull --ff-only origin "$BRANCH" || true
    _save_all
    _deploy
    ;;
  restore)
    echo "Recover einzeln via: cd $BACKEND && $BR -restore apps/cv_extractor/<rel>"
    echo "Dateien: ${FILES[*]}"
    ;;
  *)
    echo "Usage: $0 {prepare|deploy|restore}"
    exit 2
    ;;
esac
