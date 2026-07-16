#!/bin/bash
# i18n Qualitäts-Audit — Stichproben nach Full-Reset
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/email-studio-undo-i18n-bf44
#   git show origin/cursor/email-studio-undo-i18n-bf44:Repo_abpe/email_studio/incoming/RUN-i18n-audit.sh | bash
#
# Nur Email Studio:
#   ... | bash -s -- --file modules/email_studio/email_studio.json
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
BRANCH="${BRANCH:-cursor/email-studio-undo-i18n-bf44}"
BR="origin/${BRANCH}"
R="Repo_abpe/email_studio/incoming"

cd "$REPO"
git fetch origin "$BRANCH"
git show "$BR:$R/audit_i18n_quality.py" > "$REPO/$R/audit_i18n_quality.py"
chmod +x "$REPO/$R/audit_i18n_quality.py"

echo "=== i18n Qualitäts-Audit ==="
python3 "$REPO/$R/audit_i18n_quality.py" --backend "$BACKEND" --sample 4 "$@"

echo ""
echo "--- Konsistenz (Translator) ---"
cd "$BACKEND"
PYTHONWARNINGS=ignore python3 apps/abpe_ui/bin/i18n_translator.py 2>&1 | head -25
