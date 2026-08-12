#!/usr/bin/env bash
# CV-Extractor: sicherer Änderungs-Workflow (Live zuerst, Recover, kein Schema)
#
# Arbeitshandweisung (ucs5):
#   1) Live → Repo 1:1 für die Dateien der Fix-Liste
#   2) Pro Datei: backup_restore -save (Recover)
#   3) Repo ändern (Cloud/Agent) → SYNC nur diese Dateien
#   4) Test Troschke → ggf. -restore
#
# WICHTIG: Nie `prepare` NACH Agent-Fixes committen, bevor `deploy` lief —
# sonst überschreibt Live (alt) die neuen Patches im Repo (siehe c381628).
#
# Aufruf auf ucs5:
#   cd /mnt/public/udoo-reprap && bash scripts/SAFE-cv-extractor-edit.sh prepare
#   # … Agent ändert im Repo …
#   bash scripts/SAFE-cv-extractor-edit.sh deploy
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/cv-extractor-7f07}"
LIVE_CV="${LIVE_CV:-/opt/abpe/backend/apps/cv_extractor}"
SRC="$REPO/Repo_abpe/cv_extractor/incoming"
BACKEND="${BACKEND:-/opt/abpe/backend}"
BR="${BR:-python3 Archiv/backup_restore.py}"
MSG_PREFIX="${MSG_PREFIX:-cv_extractor fidelity Fix1-4}"

# Nur diese Dateien — kein models.py, keine Migrations
# (Publish + Import gegen Doppel-Pipeline / EN-Spam)
FILES=(
  extractors/main_base_extractor.py
  extractors/aid_regex_extractor.py
  generator/word/word_generator.py
  generator/html/html_generator.py
  enricher/main_extracted_to_db.py
  services/main_post_processor.py
  services/aid_profile_publish.py
  services/main_pipeline_controller.py
  management/commands/import_aid_profiles.py
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
    $BR -save "$live" -m "$MSG_PREFIX vor Änderung $(date +%Y%m%d-%H%M%S)"
  done
}

_pull_files() {
  cd "$REPO"
  git fetch origin "$BRANCH"
  git checkout "$BRANCH"
  git pull origin "$BRANCH" || true
  echo ">>> Live → Repo (1:1 nur Fix-Liste)"
  for rel in "${FILES[@]}"; do
    src="$LIVE_CV/$rel"
    dst="$SRC/$rel"
    if [[ ! -f "$src" ]]; then
      echo "SKIP (fehlt Live): $src"
      continue
    fi
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst"
    echo "OK pull $rel"
  done
  echo
  echo "Als Nächstes committen (auf ucs5):"
  echo "  cd $REPO"
  echo "  git add Repo_abpe/cv_extractor/incoming/extractors/main_base_extractor.py \\"
  echo "          Repo_abpe/cv_extractor/incoming/generator/word/word_generator.py \\"
  echo "          Repo_abpe/cv_extractor/incoming/generator/html/html_generator.py \\"
  echo "          Repo_abpe/cv_extractor/incoming/enricher/main_extracted_to_db.py \\"
  echo "          Repo_abpe/cv_extractor/incoming/services/main_post_processor.py"
  echo "  git commit -m 'chore(cv_extractor): Live→Repo Basis vor fidelity Fix1-4'"
  echo "  git push origin $BRANCH"
}

_deploy_files() {
  cd "$REPO"
  git pull origin "$BRANCH"
  echo ">>> Repo → Live (nur Fix-Liste)"
  for rel in "${FILES[@]}"; do
    src="$SRC/$rel"
    dst="$LIVE_CV/$rel"
    if [[ ! -f "$src" ]]; then
      echo "SKIP (fehlt Repo): $src"
      continue
    fi
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst"
    echo "OK deploy $rel"
  done
  echo
  echo "App/Celery neu laden, dann:"
  echo "  python3 manage.py import_aid_profiles --letter ttt --dir troschke_thomas --sync --no-skip-existing"
  echo "  ls -la /mnt/public/Berater/AID_profile/ttt/troschke_thomas/neu/cv/"
}

_restore_hint() {
  echo "Restore einer Datei (Beispiel):"
  echo "  cd $BACKEND"
  echo "  $BR -list apps/cv_extractor/generator/word/word_generator.py"
  echo "  $BR -restore apps/cv_extractor/generator/word/word_generator.py"
}

case "$cmd" in
  prepare)
    echo "======== SAFE prepare: Backup Live + Live→Repo ========"
    _save_all
    _pull_files
    ;;
  backup-only)
    _save_all
    ;;
  pull-only)
    _pull_files
    ;;
  deploy)
    echo "======== SAFE deploy: Repo→Live (nach Agent-Patch) ========"
    _save_all
    _deploy_files
    ;;
  restore-help)
    _restore_hint
    ;;
  list)
    printf '%s\n' "${FILES[@]}"
    ;;
  *)
    sed -n '2,20p' "$0"
    echo
    echo "Befehle: prepare | backup-only | pull-only | deploy | restore-help | list"
    ;;
esac
