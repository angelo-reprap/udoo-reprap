#!/usr/bin/env bash
# Nach dem fehlerhaften SYNC-posteingang-radar-fix: Inventar + Restore aus bak-pe.
#
# Auf ucs5:
#   bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/RECOVER-after-pe-sync.sh)
#   # oder nur Inventar:
#   MODE=list bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/RECOVER-after-pe-sync.sh)
#
# TS vom fehlgeschlagenen Lauf (Log: 20260818-144816) — überschreibbar.
set -euo pipefail

MODE="${MODE:-list}"   # list | restore-bak-pe | inventory-all
TS="${TS:-20260818-144816}"
LIVE_SH="${LIVE_SH:-/opt/abpe/backend/apps/abpe_shaduler}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
LIVE_NAMAZU_CMD="${LIVE_NAMAZU_CMD:-/opt/abpe/backend/apps/namazu/management/commands}"
STATICFILES="${STATICFILES:-/opt/abpe/backend/staticfiles}"
BACKEND="${BACKEND:-/opt/abpe/backend}"

echo "======== RECOVER after pe-sync MODE=$MODE TS=$TS ========"
echo

echo "=== 1) bak-pe-$TS (vom SYNC selbst) ==="
find /opt/abpe/backend/apps /opt/abpe/backend/staticfiles -name "*.bak-pe-$TS" 2>/dev/null | sort || true
echo

echo "=== 2) Weitere Side-Backups (outreach / matching-sync) ==="
find /opt/abpe/backend/apps/abpe_ui /opt/abpe/backend/apps/abpe_shaduler /opt/abpe/backend/apps/namazu \
  /opt/abpe/backend/staticfiles \
  \( -name '*.bak-outreach-*' -o -name '*.bak-before-matching-sync*' -o -name '*.bak-pe-*' \) \
  2>/dev/null | sort | tail -80 || true
echo

echo "=== 3) Shaduler mtime (neueste 40 Dateien) ==="
find "$LIVE_SH" -type f \( -name '*.py' -o -name '*.js' \) ! -path '*/__pycache__/*' \
  -printf '%T+ %p\n' 2>/dev/null | sort -r | head -40 || true
echo

echo "=== 4) UI mod-shaduler* mtime ==="
ls -la --time-style=long-iso \
  "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js" \
  "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css" \
  "$STATICFILES/abpe_ui/js/mod/mod-shaduler.js" \
  "$STATICFILES/abpe_ui/css/mod/mod-shaduler.css" \
  2>/dev/null || true
echo

echo "=== 5) backup_restore Archiv (abpe_ui) — letzte Einträge ==="
if [[ -f "$BACKEND/apps/abpe_ui/backup_restore.py" ]]; then
  cd "$BACKEND"
  /opt/abpe/venv311/bin/python apps/abpe_ui/backup_restore.py -list 2>/dev/null | tail -40 || true
  echo "--- Suche shaduler/matching ---"
  /opt/abpe/venv311/bin/python apps/abpe_ui/backup_restore.py -list 2>/dev/null \
    | grep -iE 'shaduler|mod-matching|mod-shaduler|index_emails' | tail -40 || true
else
  echo "backup_restore.py nicht gefunden"
fi
echo

echo "=== 6) /opt/abpe/backups/* (Dirs) ==="
ls -lt /opt/abpe/backups 2>/dev/null | head -30 || true
echo

if [[ "$MODE" == "list" || "$MODE" == "inventory-all" ]]; then
  echo "Nur Inventar. Restore:"
  echo "  MODE=restore-bak-pe TS=$TS bash scripts/RECOVER-after-pe-sync.sh"
  echo
  echo "WICHTIG: bak-pe gibt es nur für Dateien, die das SYNC einzeln gesichert hat:"
  echo "  - namazu/.../index_emails.py.bak-pe-$TS"
  echo "  - mod-shaduler.js / .css (.bak-pe-$TS)"
  echo "  Das rsync von abpe_shaduler/ hatte KEIN per-file bak — dort:"
  echo "  - ältere *.bak-before-matching-sync* / *.bak-outreach-*"
  echo "  - oder backup_restore -list / -restore"
  echo "  - oder Live-Pull aus einem älteren Backup-Dir unter /opt/abpe/backups/"
  exit 0
fi

if [[ "$MODE" != "restore-bak-pe" ]]; then
  echo "Unbekannter MODE=$MODE"
  exit 1
fi

echo "=== RESTORE bak-pe-$TS → Live (nur vorhandene bak) ==="
restored=0
while IFS= read -r bak; do
  [[ -f "$bak" ]] || continue
  live="${bak%.bak-pe-$TS}"
  if [[ ! -f "$live" ]]; then
    echo "SKIP (kein Live-Ziel): $bak"
    continue
  fi
  cp -a "$live" "${live}.before-recover-$TS" 2>/dev/null || true
  cp -a "$bak" "$live"
  echo "RESTORED $bak → $live"
  restored=$((restored + 1))
done < <(find /opt/abpe/backend/apps /opt/abpe/backend/staticfiles -name "*.bak-pe-$TS" 2>/dev/null | sort)

# staticfiles mirror für UI
if [[ -f "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js" && -d "$STATICFILES/abpe_ui/js/mod" ]]; then
  cp -a "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js" \
    "$STATICFILES/abpe_ui/js/mod/mod-shaduler.js"
  echo "OK staticfiles mod-shaduler.js"
fi
if [[ -f "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css" && -d "$STATICFILES/abpe_ui/css/mod" ]]; then
  cp -a "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css" \
    "$STATICFILES/abpe_ui/css/mod/mod-shaduler.css"
  echo "OK staticfiles mod-shaduler.css"
fi

echo
echo "Restored $restored bak-pe files."
echo "Shaduler-Python-Tree wurde vom SYNC OHNE bak überschrieben — bak-pe hilft dort nicht."
echo "Als Nächstes Inventar der älteren Side-Backups prüfen und gezielt zurückkopieren."
echo "  supervisorctl restart abpe-django abpe-celery"
echo "  Ctrl+F5"
