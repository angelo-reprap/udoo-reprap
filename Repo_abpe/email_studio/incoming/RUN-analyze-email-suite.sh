#!/bin/bash
# Email Studio + Composer — Analyse & Funktionstests (ucs5)
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/email-studio-undo-i18n-bf44
#   bash Repo_abpe/email_studio/incoming/RUN-analyze-email-suite.sh
#
# Mit schreibenden Tests (legt Temp-Vorlage an und archiviert sie):
#   bash Repo_abpe/email_studio/incoming/RUN-analyze-email-suite.sh --mutate
#
# Mit JSON-Report:
#   bash Repo_abpe/email_studio/incoming/RUN-analyze-email-suite.sh --json /tmp/email-analyze.json
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
SCRIPT="$REPO/Repo_abpe/email_studio/incoming/analyze_email_suite.py"
BRANCH="${BRANCH:-cursor/email-studio-undo-i18n-bf44}"

_activate_venv() {
  if [[ -n "${VIRTUAL_ENV:-}" ]]; then return 0; fi
  for candidate in "/opt/abpe/venv311/bin/activate" "/opt/abpe/backend/venv311/bin/activate"; do
    [[ -f "$candidate" ]] || continue
    # shellcheck disable=SC1090
    source "$candidate"
    return 0
  done
}

echo "=== Email Suite Analyse ==="
echo "Backend: $BACKEND"
echo "Repo:    $REPO"

if [[ -d "$REPO/.git" ]]; then
  git -C "$REPO" fetch origin "$BRANCH" 2>/dev/null || true
  git -C "$REPO" show "origin/$BRANCH:Repo_abpe/email_studio/incoming/analyze_email_suite.py" \
    > "$SCRIPT" 2>/dev/null || true
fi

if [[ ! -f "$SCRIPT" ]]; then
  echo "FEHLER: analyze_email_suite.py nicht gefunden: $SCRIPT"
  exit 1
fi

chmod +x "$SCRIPT"
_activate_venv

cd "$BACKEND"
python3 "$SCRIPT" \
  --backend "$BACKEND" \
  --repo "$REPO" \
  --template-id "${TEMPLATE_ID:-13}" \
  "$@"
