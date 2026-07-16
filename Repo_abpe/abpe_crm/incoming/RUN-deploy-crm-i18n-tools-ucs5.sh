#!/bin/bash
# CRM i18n tools: module.json + modules.json titles support
# Backup → Deploy (ucs5)
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/portal-i18n-phase1-bf44
#   git show origin/cursor/portal-i18n-phase1-bf44:Repo_abpe/abpe_crm/incoming/RUN-deploy-crm-i18n-tools-ucs5.sh | bash

set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${ABPE_BACKEND:-/opt/abpe/backend}"
BR="${BR:-origin/cursor/portal-i18n-phase1-bf44}"
NOTE="${NOTE:-vor crm-i18n-tools}"
BR_PY="$BACKEND/Archiv/backup_restore.py"

cd "$REPO"
git fetch origin cursor/portal-i18n-phase1-bf44 2>/dev/null || true

backup() {
  local rel="$1"
  if [[ -f "$BACKEND/$rel" ]]; then
    python3 "$BR_PY" -save "$rel" -m "$NOTE"
    echo "BACKUP: $rel"
  fi
}

deploy() {
  local src="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  git show "$BR:$src" > "$dest"
  chmod +x "$dest" 2>/dev/null || true
  echo "OK: $dest"
}

echo "=== 1. BACKUP ==="
backup apps/abpe_crm/bin/i18n_translator.py
backup apps/abpe_crm/bin/i18n_validate.py

echo ""
echo "=== 2. DEPLOY ==="
deploy Repo_abpe/abpe_crm/incoming/i18n_translator.py \
  "$BACKEND/apps/abpe_crm/bin/i18n_translator.py"
deploy Repo_abpe/abpe_crm/incoming/i18n_validate.py \
  "$BACKEND/apps/abpe_crm/bin/i18n_validate.py"

echo ""
echo "=== 3. Test (nur Check, kein API) ==="
cd "$BACKEND"
if [[ -f venv311/bin/activate ]]; then source venv311/bin/activate
elif [[ -f venv/bin/activate ]]; then source venv/bin/activate
fi
python3 apps/abpe_crm/bin/i18n_translator.py --check || true

echo ""
echo "Fertig. Übersetzen:"
echo "  python3 apps/abpe_crm/bin/i18n_translator.py"
echo "  python3 apps/abpe_crm/bin/i18n_validate.py --fix"
