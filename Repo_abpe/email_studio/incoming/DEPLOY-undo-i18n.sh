#!/bin/bash
# Email Studio — i18n + Undo/Milestone (ucs5)
#
# WICHTIG: git fetch allein aktualisiert NICHT den Working Tree!
# Nach fetch den Branch-Inhalt per git show laden:
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/email-studio-undo-i18n-bf44
#   git show origin/cursor/email-studio-undo-i18n-bf44:Repo_abpe/email_studio/incoming/DEPLOY-undo-i18n.sh | bash
#
# Alternativ (wenn Datei lokal existiert):
#   bash Repo_abpe/email_studio/incoming/DEPLOY-undo-i18n.sh
#
set -euo pipefail

BACKEND=/opt/abpe/backend
REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/email-studio-undo-i18n-bf44}"
BR="origin/${BRANCH}"
R="Repo_abpe/email_studio/incoming"

_activate_venv() {
  if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    echo "venv bereits aktiv: $VIRTUAL_ENV"
    return 0
  fi
  local candidates=(
    "${VENV:-}"
    "/opt/abpe/venv311/bin/activate"
    "/opt/abpe/backend/venv311/bin/activate"
  )
  for candidate in "${candidates[@]}"; do
    [[ -n "$candidate" && -f "$candidate" ]] || continue
    # shellcheck disable=SC1090
    source "$candidate"
    echo "venv aktiviert: $candidate"
    return 0
  done
  echo "WARN: kein venv gefunden — nutze aktuelles python ($(command -v python || echo '?'))"
  return 0
}

if [[ ! -d "$REPO/.git" ]]; then
  echo "FEHLER: Git-Repo nicht gefunden unter: $REPO"
  exit 1
fi

echo "=== Email Studio Undo/i18n Deploy ==="
echo "Repo:   $REPO"
echo "Branch: $BRANCH"
cd "$REPO"
git fetch origin "$BRANCH"

# Template (nicht collectstatic!)
git show "$BR:$R/studio.html" > "$BACKEND/apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html"

# JS + CSS + API
git show "$BR:$R/es-studio.js" > "$BACKEND/apps/abpe_email_studio/static/email_studio/js/es-studio.js"
git show "$BR:$R/mod-email_studio.css" > "$BACKEND/apps/abpe_ui/static/abpe_ui/css/mod/mod-email_studio.css"
git show "$BR:$R/api.py" > "$BACKEND/apps/abpe_email_studio/api.py"

# i18n: Archiv-Backup → nur DE → i18n_translator (sauber & konsistent)
git show "$BR:$R/RUN-i18n-reset-translator.sh" | bash -s --

echo "✓ Fertig — Strg+Shift+R"
