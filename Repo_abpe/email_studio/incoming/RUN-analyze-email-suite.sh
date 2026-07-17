#!/bin/bash
# Email Studio + Composer — Analyse & Funktionstests (ucs5)
#
# WICHTIG: git fetch allein aktualisiert NICHT den Working Tree!
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/email-studio-undo-i18n-bf44
#   git show origin/cursor/email-studio-undo-i18n-bf44:Repo_abpe/email_studio/incoming/RUN-analyze-email-suite.sh | bash
#
# Mit schreibenden Tests:
#   git show origin/cursor/...:.../RUN-analyze-email-suite.sh | bash -s -- --mutate
#
# Mit JSON-Report:
#   git show origin/cursor/...:.../RUN-analyze-email-suite.sh | bash -s -- --json /tmp/email-analyze.json
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
BRANCH="${BRANCH:-cursor/email-studio-undo-i18n-bf44}"
BR="origin/${BRANCH}"
R="Repo_abpe/email_studio/incoming"
SCRIPT="$REPO/$R/analyze_email_suite.py"

_activate_venv() {
  if [[ -n "${VIRTUAL_ENV:-}" ]]; then return 0; fi
  for candidate in "/opt/abpe/venv311/bin/activate" "/opt/abpe/backend/venv311/bin/activate"; do
    [[ -f "$candidate" ]] || continue
    # shellcheck disable=SC1090
    source "$candidate"
    return 0
  done
}

if [[ ! -d "$REPO/.git" ]]; then
  echo "FEHLER: Git-Repo nicht gefunden: $REPO"
  exit 1
fi

echo "=== Email Suite Analyse ==="
echo "Backend: $BACKEND"
echo "Repo:    $REPO"
echo "Branch:  $BRANCH"

cd "$REPO"
git fetch origin "$BRANCH"

mkdir -p "$REPO/$R"
git show "$BR:$R/analyze_email_suite.py" > "$SCRIPT"
chmod +x "$SCRIPT"

_activate_venv
cd "$BACKEND"
python3 "$SCRIPT" \
  --backend "$BACKEND" \
  --repo "$REPO" \
  --template-id "${TEMPLATE_ID:-13}" \
  "$@"
