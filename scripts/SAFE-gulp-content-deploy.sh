#!/usr/bin/env bash
# SAFE Deploy: Gulp-Inhalt — NUR nach Live↔Repo 1:1 Prüfung
#
# REGEL (vom Betreiber): Keine Datei ändern/deployen, die nicht geprüft
# aktuell 1:1 Live↔Repo ist. prepare kopiert Live → Repo-Sidecar + Diff.
#
#   bash scripts/SAFE-gulp-content-deploy.sh prepare
#     → backup_restore -save
#     → Live → Repo_abpe/.../*.live-copy-<ts>
#     → diff Live vs Repo (zeigt Drift)
#     → KEIN Überschreiben von Live
#
#   # Bei Drift zuerst Repo auf Live bringen:
#   bash scripts/SAFE-gulp-content-deploy.sh sync-from-live
#   git add … && git commit && git push
#   # dann Agent-Patches auf diesem Stand, erneut prepare → 1:1 oder nur bewusster Diff
#
#   bash scripts/SAFE-gulp-content-deploy.sh deploy
#     → bricht ab wenn Drift (FORCE=1 nur bewusst)
#
#   bash scripts/SAFE-gulp-content-deploy.sh restore
#     → backup_restore -restore
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/gulp-keyword-pipeline-1532}"
LIVE_CV="${LIVE_CV:-/opt/abpe/backend/apps/cv_extractor}"
SRC="$REPO/Repo_abpe/cv_extractor/incoming"
BACKEND="${BACKEND:-/opt/abpe/backend}"
BR="${BR:-python3 Archiv/backup_restore.py}"
MSG_PREFIX="${MSG_PREFIX:-gulp content Wohnort/Skills}"
FORCE="${FORCE:-0}"
STATE_DIR="$REPO/artifacts/safe-gulp-content"
DRIFT_FLAG="$STATE_DIR/last-prepare-had-drift"

FILES=(
  extractors/aid_regex_extractor.py
  services/main_db_importer.py
  services/url_fl_db_importer.py
  management/commands/cleanup_aid_test_imports.py
)

cmd="${1:-help}"
ts="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$STATE_DIR"

_save_all() {
  cd "$BACKEND"
  for rel in "${FILES[@]}"; do
    live="apps/cv_extractor/$rel"
    if [[ ! -f "$live" ]]; then
      echo "SKIP (fehlt Live): $live"
      continue
    fi
    echo ">>> -save $live"
    $BR -save "$live" -m "$MSG_PREFIX $1 $(date +%Y%m%d-%H%M%S)"
  done
}

_prepare() {
  cd "$REPO"
  git fetch origin "$BRANCH" 2>/dev/null || true
  git checkout "$BRANCH" 2>/dev/null || true
  git pull --ff-only origin "$BRANCH" 2>/dev/null || true

  echo "=== 1) backup_restore -save (Live sichern) ==="
  _save_all "prepare"

  echo
  echo "=== 2) Live → Sidecar-Kopien + Diff vs Repo ==="
  rm -f "$DRIFT_FLAG"
  drift=0
  for rel in "${FILES[@]}"; do
    live="$LIVE_CV/$rel"
    repo="$SRC/$rel"
    side="$SRC/${rel}.live-copy-$ts"
    if [[ ! -f "$live" ]]; then
      echo "SKIP Live fehlt: $live"
      continue
    fi
    mkdir -p "$(dirname "$side")"
    cp -a "$live" "$side"
    echo "OK live-copy → $side"
    if [[ ! -f "$repo" ]]; then
      echo "WARN Repo fehlt: $repo"
      drift=1
      continue
    fi
    if ! cmp -s "$live" "$repo"; then
      echo "DRIFT $rel  (Live ≠ Repo)"
      echo "  diff -u $side $repo | head -80"
      diff -u "$side" "$repo" | head -40 || true
      echo "  ---"
      drift=1
    else
      echo "OK 1:1 $rel"
    fi
  done

  if [[ "$drift" -eq 1 ]]; then
    touch "$DRIFT_FLAG"
    echo
    echo "⚠ DRIFT — Repo ist NICHT 1:1 mit Live."
    echo "  → Agent-Patches erst auf Live-Stand neu basieren / mergen."
    echo "  → deploy ist GESPERRT bis FORCE=1 (nur bewusst)."
    echo "  Sidecars: $SRC/*live-copy-$ts"
  else
    rm -f "$DRIFT_FLAG"
    echo
    echo "OK: alle ${#FILES[@]} Dateien Live ↔ Repo 1:1."
    echo "  deploy erlaubt: bash $0 deploy"
  fi
}

_deploy() {
  if [[ -f "$DRIFT_FLAG" && "$FORCE" != "1" ]]; then
    echo "FAIL: letztes prepare hatte Drift. Kein Deploy ohne Live↔Repo 1:1." >&2
    echo "  Neu: bash $0 prepare" >&2
    echo "  Oder bewusst: FORCE=1 bash $0 deploy" >&2
    exit 1
  fi

  echo "=== Pre-check: Live vs Repo jetzt ==="
  for rel in "${FILES[@]}"; do
    live="$LIVE_CV/$rel"
    repo="$SRC/$rel"
    if [[ ! -f "$live" || ! -f "$repo" ]]; then
      echo "FAIL fehlt: $rel" >&2
      exit 1
    fi
    if ! cmp -s "$live" "$repo"; then
      if [[ "$FORCE" != "1" ]]; then
        echo "FAIL Drift jetzt bei $rel — abbruch (FORCE=1 zum Überschreiben)" >&2
        diff -u "$live" "$repo" | head -30 || true
        exit 1
      fi
      echo "WARN FORCE: deploy trotz Drift $rel"
    fi
  done

  _save_all "vor-deploy"
  echo "=== Repo → Live ==="
  for rel in "${FILES[@]}"; do
    src="$SRC/$rel"
    dst="$LIVE_CV/$rel"
    cp -a "$src" "$dst"
    echo "OK deploy $rel"
  done
  echo "OK deployed. gulp_profile_clean bleibt Repo-only (CONVERT)."
}

_restore() {
  echo "=== restore letzten -save Stand (vor diesem Deploy) ==="
  cd "$BACKEND"
  for rel in "${FILES[@]}"; do
    live="apps/cv_extractor/$rel"
    echo ">>> -restore $live"
    $BR -restore "$live" || echo "WARN restore fehlgeschlagen: $live"
  done
  echo "Fertig. Diff prüfen: bash $0 prepare"
}

_sync_from_live() {
  # Live → Repo (1:1 Basis). Danach commit+push, erst dann Agent-Patches.
  echo "=== Live → Repo (überschreibt Repo-Stand dieser Dateien) ==="
  for rel in "${FILES[@]}"; do
    live="$LIVE_CV/$rel"
    repo="$SRC/$rel"
    if [[ ! -f "$live" ]]; then
      echo "FAIL Live fehlt: $live" >&2
      exit 1
    fi
    mkdir -p "$(dirname "$repo")"
    cp -a "$live" "$repo"
    echo "OK sync $rel"
  done
  rm -f "$DRIFT_FLAG"
  echo
  echo "Als Nächstes auf ucs5:"
  echo "  cd $REPO"
  echo "  git add \\"
  for rel in "${FILES[@]}"; do
    echo "    Repo_abpe/cv_extractor/incoming/$rel \\"
  done
  echo "    && git commit -m 'chore: Live→Repo 1:1 (SAFE content) before patch' \\"
  echo "    && git push origin $BRANCH"
  echo "  # danach Agent: Patches auf diesem Stand neu setzen"
  echo "  bash $0 prepare   # muss OK 1:1 zeigen"
}

case "$cmd" in
  prepare) _prepare ;;
  deploy)  _deploy ;;
  restore) _restore ;;
  sync-from-live) _sync_from_live ;;
  save)    _save_all "manual" ;;
  help|*)
    sed -n '2,25p' "$0"
    echo "Usage: $0 {prepare|sync-from-live|deploy|restore|save}"
    exit 0
    ;;
esac
