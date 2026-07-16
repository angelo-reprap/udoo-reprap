#!/bin/bash
# i18n — Konsistenz prüfen, bei Bedarf Fremdsprachen löschen, Translator neu
#
# RICHTIGER Translator (ucs5):
#   apps/abpe_ui/bin/i18n_translator.py
# NICHT apps/abpe_crm/bin/i18n_translator.py
#
# Nur Konsistenz-Check (kein Löschen):
#   bash Repo_abpe/email_studio/incoming/RUN-i18n-check-and-reset.sh --check-only
#
# Nur Email-Studio-Modul reset:
#   bash .../RUN-i18n-check-and-reset.sh --email-studio-only
#
# Komplette Fremdsprachen löschen + Translator (dauert ~15–30 Min):
#   bash .../RUN-i18n-check-and-reset.sh --full-reset
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
I18N_REL="apps/abpe_ui/static/abpe_ui/i18n"
LANGS=(ar en es fr it ja ko nl pl pt ru tr zh)
EMAIL_STUDIO_REL="modules/email_studio/email_studio.json"
TRANSLATOR="apps/abpe_ui/bin/i18n_translator.py"
NOTE="i18n-reset $(date +%Y-%m-%d_%H%M)"
MODE="${1:-}"

_activate_venv() {
  if [[ -n "${VIRTUAL_ENV:-}" ]]; then return 0; fi
  for candidate in "/opt/abpe/venv311/bin/activate" "/opt/abpe/backend/venv311/bin/activate"; do
    [[ -f "$candidate" ]] || continue
    # shellcheck disable=SC1090
    source "$candidate"
    return 0
  done
}

_run_translator() {
  cd "$BACKEND"
  _activate_venv
  if [[ ! -f "$TRANSLATOR" ]]; then
    echo "FEHLER: $TRANSLATOR nicht gefunden"
    exit 1
  fi
  PYTHONWARNINGS=ignore python3 "$TRANSLATOR" 2>&1 | tee /tmp/i18n_translator_last.log
}

_count_problems() {
  local log="${1:-/tmp/i18n_translator_last.log}"
  if [[ ! -f "$log" ]]; then
    echo 999
    return
  fi
  grep -c "Problem(e)" "$log" 2>/dev/null || echo 0
}

_check_email_studio_files() {
  cd "$BACKEND"
  local missing=0
  for lang in de "${LANGS[@]}"; do
    local f="$I18N_REL/$lang/$EMAIL_STUDIO_REL"
    if [[ -f "$f" ]]; then
      echo "  OK   $lang → $EMAIL_STUDIO_REL"
    else
      echo "  FEHLT $lang → $EMAIL_STUDIO_REL"
      missing=$((missing + 1))
    fi
  done
  return "$missing"
}

_backup_lang_jsons() {
  local lang="$1"
  local archiv="$BACKEND/Archiv/backup_restore.py"
  cd "$BACKEND"
  local dir="$I18N_REL/$lang"
  [[ -d "$dir" ]] || return 0
  find "$dir" -name '*.json' -type f | while read -r f; do
    python3 "$archiv" -save "$f" -m "$NOTE"
  done
}

_backup_all_non_de() {
  cd "$BACKEND"
  echo "--- Archiv-Backup aller Fremdsprachen-JSONs ($NOTE) ---"
  for lang in "${LANGS[@]}"; do
    echo "  Backup: $lang"
    _backup_lang_jsons "$lang"
  done
  echo "✓ Backup fertig"
}

_delete_email_studio_non_de() {
  cd "$BACKEND"
  local n=0
  for lang in "${LANGS[@]}"; do
    local f="$I18N_REL/$lang/$EMAIL_STUDIO_REL"
    if [[ -f "$f" ]]; then
      rm -f "$f"
      echo "  gelöscht: $lang/$EMAIL_STUDIO_REL"
      n=$((n + 1))
    fi
  done
  echo "✓ $n email_studio.json entfernt"
}

_delete_all_non_de() {
  cd "$BACKEND"
  for lang in "${LANGS[@]}"; do
    if [[ -d "$I18N_REL/$lang" ]]; then
      rm -rf "$I18N_REL/$lang"
      echo "  gelöscht: $I18N_REL/$lang/"
    fi
  done
  echo "✓ Alle Fremdsprach-Verzeichnisse entfernt (nur de/ bleibt)"
}

_create_lang_dirs() {
  cd "$BACKEND"
  for lang in "${LANGS[@]}"; do
    mkdir -p "$I18N_REL/$lang"
    echo "  angelegt: $I18N_REL/$lang/"
  done
  echo "✓ Leere Sprachordner angelegt (Translator braucht diese!)"
}

_finish() {
  cd "$BACKEND"
  _activate_venv
  PYTHONWARNINGS=ignore python manage.py collectstatic --noinput
  supervisorctl restart abpe-django
  echo "✓ collectstatic + restart — Strg+Shift+R"
}

echo "=== i18n Check & Reset ==="
echo "Backend:    $BACKEND"
echo "Translator: $TRANSLATOR"

if [[ "$MODE" == "--check-only" ]]; then
  echo ""
  echo "--- Konsistenz (Translator-Lauf) ---"
  _run_translator
  echo ""
  echo "--- email_studio.json pro Sprache ---"
  _check_email_studio_files || true
  problems=$(_count_problems)
  echo ""
  if [[ "$problems" -eq 0 ]]; then
    echo "✓ Keine Konsistenz-Probleme in der letzten Ausgabe"
  else
    echo "⚠ $problems Sprache(n) mit Problemen — siehe Log oben"
  fi
  exit 0
fi

if [[ "$MODE" == "--email-studio-only" ]]; then
  echo ""
  echo "--- 1/4 Archiv-Backup (email_studio) ---"
  cd "$BACKEND"
  for lang in de "${LANGS[@]}"; do
    local_f="$I18N_REL/$lang/$EMAIL_STUDIO_REL"
    [[ -f "$local_f" ]] && python3 Archiv/backup_restore.py -save "$local_f" -m "$NOTE"
  done
  echo ""
  echo "--- 2/4 email_studio.json löschen (nur Fremdsprachen) ---"
  _delete_email_studio_non_de
  echo ""
  echo "--- 3/4 Translator ---"
  _run_translator
  echo ""
  echo "--- 4/4 Deploy ---"
  _finish
  exit 0
fi

if [[ "$MODE" == "--full-reset" ]]; then
  echo ""
  echo "--- 1/4 Archiv-Backup (alle JSONs in Fremdsprachen) ---"
  _backup_all_non_de
  echo ""
  echo "--- 2/5 Fremdsprach-Verzeichnisse löschen ---"
  _delete_all_non_de
  echo ""
  echo "--- 3/5 Leere Sprachordner anlegen (mkdir) ---"
  _create_lang_dirs
  echo ""
  echo "--- 4/5 Translator (alle ~79 Dateien × 13 Sprachen — dauert!) ---"
  _run_translator
  echo ""
  echo "--- 5/5 Deploy ---"
  _finish
  exit 0
fi

# Standard: prüfen → bei Problemen email_studio reset → nochmal prüfen
echo ""
echo "--- Schritt 1: Konsistenz prüfen ---"
_run_translator
problems=$(_count_problems)

if [[ "$problems" -eq 0 ]]; then
  echo ""
  echo "✓ Konsistenz OK — nichts zu tun"
  _check_email_studio_files || true
  exit 0
fi

echo ""
echo "⚠ $problems Sprache(n) mit Problemen — email_studio reset"
echo ""
echo "--- Schritt 2: Archiv + email_studio löschen ---"
cd "$BACKEND"
for lang in de "${LANGS[@]}"; do
  local_f="$I18N_REL/$lang/$EMAIL_STUDIO_REL"
  [[ -f "$local_f" ]] && python3 Archiv/backup_restore.py -save "$local_f" -m "$NOTE"
done
_delete_email_studio_non_de

echo ""
echo "--- Schritt 3: Translator erneut ---"
_run_translator

echo ""
echo "--- Schritt 4: Deploy ---"
_finish

echo ""
echo "--- Schritt 5: Finale Prüfung ---"
_check_email_studio_files || true
