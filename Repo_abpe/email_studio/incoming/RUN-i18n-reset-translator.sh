#!/bin/bash
# Email Studio i18n — Archiv-Backup, Fremdsprachen löschen, i18n_translator neu
#
# WICHTIG: Löscht alle email_studio.json außer DE und lässt den globalen
# CRM-Translator alle Sprachen frisch aus DE generieren.
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/email-studio-undo-i18n-bf44
#   git show origin/cursor/email-studio-undo-i18n-bf44:Repo_abpe/email_studio/incoming/RUN-i18n-reset-translator.sh | bash
#
# Nur Backup (kein Löschen):
#   ... | bash -s -- --backup-only
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
BRANCH="${BRANCH:-cursor/email-studio-undo-i18n-bf44}"
BR="origin/${BRANCH}"
R="Repo_abpe/email_studio/incoming"
NOTE="email-studio i18n-reset $(date +%Y-%m-%d_%H%M)"
I18N_REL="apps/abpe_ui/static/abpe_ui/i18n"
MODULE_REL="modules/email_studio/email_studio.json"
LANGS=(ar de en es fr it ja ko nl pl pt ru tr zh)

_activate_venv() {
  if [[ -n "${VIRTUAL_ENV:-}" ]]; then return 0; fi
  for candidate in "/opt/abpe/venv311/bin/activate" "/opt/abpe/backend/venv311/bin/activate"; do
    [[ -f "$candidate" ]] || continue
    # shellcheck disable=SC1090
    source "$candidate"
    return 0
  done
}

_backup_all() {
  local archiv="$BACKEND/Archiv/backup_restore.py"
  if [[ ! -f "$archiv" ]]; then
    echo "FEHLER: Archiv/backup_restore.py nicht gefunden: $archiv"
    exit 1
  fi
  cd "$BACKEND"
  local n=0
  for lang in "${LANGS[@]}"; do
    local rel="$I18N_REL/$lang/$MODULE_REL"
    if [[ -f "$rel" ]]; then
      python3 Archiv/backup_restore.py -save "$rel" -m "$NOTE"
      n=$((n + 1))
    fi
  done
  echo "✓ Archiv-Backup: $n Dateien ($NOTE)"
}

_sync_de_canonical() {
  git show "$BR:$R/email_studio.json" > "$REPO/$R/email_studio.json"
  local dest="$BACKEND/$I18N_REL/de/$MODULE_REL"
  mkdir -p "$(dirname "$dest")"
  cp "$REPO/$R/email_studio.json" "$dest"
  echo "✓ DE kanonisch geschrieben: $dest"
}

_delete_non_de() {
  local n=0
  for lang in "${LANGS[@]}"; do
    [[ "$lang" == "de" ]] && continue
    local f="$BACKEND/$I18N_REL/$lang/$MODULE_REL"
    if [[ -f "$f" ]]; then
      rm -f "$f"
      echo "  gelöscht: $lang/modules/email_studio/email_studio.json"
      n=$((n + 1))
    fi
  done
  echo "✓ $n Fremdsprachen-Dateien entfernt (nur DE bleibt)"
}

_run_translator() {
  cd "$BACKEND"
  _activate_venv
  if [[ ! -f apps/abpe_crm/bin/i18n_translator.py ]]; then
    echo "FEHLER: apps/abpe_crm/bin/i18n_translator.py nicht gefunden"
    exit 1
  fi
  echo "--- i18n_translator (alle Module, Email Studio fehlt in Fremdsprachen) ---"
  PYTHONWARNINGS=ignore python3 apps/abpe_crm/bin/i18n_translator.py
}

_finish() {
  cd "$BACKEND"
  _activate_venv
  echo "--- collectstatic + restart ---"
  PYTHONWARNINGS=ignore python manage.py collectstatic --noinput
  supervisorctl restart abpe-django
  echo "✓ Fertig — Strg+Shift+R"
  echo ""
  echo "Rollback bei Bedarf (Beispiel FR):"
  echo "  cd $BACKEND"
  echo "  python3 Archiv/backup_restore.py -restore $I18N_REL/fr/$MODULE_REL"
}

MODE="${1:-}"

echo "=== Email Studio i18n RESET + i18n_translator ==="
echo "Backend: $BACKEND"
echo "Branch:  $BRANCH"

cd "$REPO"
git fetch origin "$BRANCH"

echo ""
echo "--- 1/5 Archiv-Backup ---"
_backup_all

if [[ "$MODE" == "--backup-only" ]]; then
  echo "(--backup-only — Abbruch vor Löschen)"
  exit 0
fi

echo ""
echo "--- 2/5 DE kanonisch aus Repo ---"
_sync_de_canonical

echo ""
echo "--- 3/5 Fremdsprachen email_studio.json löschen ---"
_delete_non_de

echo ""
echo "--- 4/5 i18n_translator ---"
_run_translator

echo ""
echo "--- 5/5 Deploy static ---"
_finish
