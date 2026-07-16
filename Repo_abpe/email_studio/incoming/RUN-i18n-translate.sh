#!/bin/bash
# Email Studio i18n — Patch + Translate + collectstatic (ucs5)
#
#   git fetch origin cursor/email-studio-undo-i18n-bf44
#   git show origin/cursor/email-studio-undo-i18n-bf44:Repo_abpe/email_studio/incoming/RUN-i18n-translate.sh | bash
#
# Nur Audit (verdächtige Keys anzeigen):
#   git show origin/.../RUN-i18n-translate.sh | bash -s -- --audit
#
# Verdächtige Keys korrigieren (noch DE / EN-Platzhalter / leer):
#   git show origin/.../RUN-i18n-translate.sh | bash -s -- --fix-suspect
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
BRANCH="${BRANCH:-cursor/email-studio-undo-i18n-bf44}"
BR="origin/${BRANCH}"
R="Repo_abpe/email_studio/incoming"

_activate_venv() {
  if [[ -n "${VIRTUAL_ENV:-}" ]]; then return 0; fi
  for candidate in "/opt/abpe/venv311/bin/activate" "/opt/abpe/backend/venv311/bin/activate"; do
    [[ -f "$candidate" ]] || continue
    # shellcheck disable=SC1090
    source "$candidate"
    return 0
  done
}

cd "$REPO"
git fetch origin "$BRANCH"
mkdir -p "$REPO/$R/i18n/en"

git show "$BR:$R/email_studio.json" > "$REPO/$R/email_studio.json"
git show "$BR:$R/i18n/en/email_studio.json" > "$REPO/$R/i18n/en/email_studio.json"
git show "$BR:$R/patch_email_studio_i18n.py" > "$REPO/$R/patch_email_studio_i18n.py"
git show "$BR:$R/translate_email_studio_i18n.py" > "$REPO/$R/translate_email_studio_i18n.py"
chmod +x "$REPO/$R/patch_email_studio_i18n.py" "$REPO/$R/translate_email_studio_i18n.py"

_activate_venv

MODE="${1:-}"
shift || true

echo "=== Email Studio i18n ==="

if [[ "$MODE" == "--audit" ]]; then
  PYTHONWARNINGS=ignore python3 "$REPO/$R/translate_email_studio_i18n.py" --backend "$BACKEND" --repo "$REPO" --audit "$@"
  exit 0
fi

if [[ "$MODE" != "--skip-patch" ]]; then
  echo "--- Patch (DE kanonisch, fehlende Keys) ---"
  python3 "$REPO/$R/patch_email_studio_i18n.py" --backend "$BACKEND" --repo "$REPO"
fi

if [[ "$MODE" == "--fix-suspect" ]]; then
  echo "--- Translate: nur verdächtige Keys ---"
  PYTHONWARNINGS=ignore python3 "$REPO/$R/translate_email_studio_i18n.py" \
    --backend "$BACKEND" --repo "$REPO" --fix-suspect "$@"
elif [[ "$MODE" == "--dry-run" ]]; then
  python3 "$REPO/$R/translate_email_studio_i18n.py" --backend "$BACKEND" --repo "$REPO" --dry-run "$@"
  exit 0
else
  echo "--- Translate (Deepseek) ---"
  PYTHONWARNINGS=ignore python3 "$REPO/$R/translate_email_studio_i18n.py" \
    --backend "$BACKEND" --repo "$REPO" "$@"
fi

if [[ "$MODE" != "--dry-run" && "$MODE" != "--audit" ]]; then
  echo "--- collectstatic ---"
  cd "$BACKEND"
  PYTHONWARNINGS=ignore python manage.py collectstatic --noinput
  supervisorctl restart abpe-django
  echo "✓ Fertig — Strg+Shift+R"
fi
