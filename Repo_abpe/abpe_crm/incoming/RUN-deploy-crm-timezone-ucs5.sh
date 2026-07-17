#!/usr/bin/env bash
# CRM Zeitzone: Git → Live (ucs5)
#
#   cd /mnt/public/udoo-reprap && git pull
#   bash Repo_abpe/abpe_crm/incoming/RUN-deploy-crm-timezone-ucs5.sh
#   cd /opt/abpe/backend && python manage.py collectstatic --noinput
#   supervisorctl restart abpe-django
#
# Backend-Patch (models + views) + Migration:
#   python Repo_abpe/abpe_crm/incoming/patches/apply_user_timezone.py
#   cd /opt/abpe/backend && python manage.py makemigrations abpe_crm --name crmusersettings_timezone
#   python manage.py migrate abpe_crm --noinput

set -euo pipefail

REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
BACKEND="${ABPE_BACKEND:-/opt/abpe/backend}"
CRM_STATIC="${ABPE_CRM_STATIC_DIR:-${BACKEND}/apps/abpe_crm/static/abpe_crm}"
CRM_TEMPLATES="${ABPE_CRM_TEMPLATES:-${BACKEND}/apps/abpe_crm/templates/abpe_crm}"

echo "Repo:    $REPO"
echo "Backend: $BACKEND"
echo ""

copy_file() {
  local src="$1" dest="$2"
  if [[ ! -f "$src" ]]; then
    echo "FEHLER: $src fehlt — git pull?" >&2
    exit 1
  fi
  mkdir -p "$(dirname "$dest")"
  cp -a "$src" "$dest"
  echo "OK: $src -> $dest"
}

echo "--- Frontend JS ---"
copy_file "${REPO}/Repo_abpe/abpe_crm/incoming/js/core-timezone.js" \
          "${CRM_STATIC}/js/core-timezone.js"
copy_file "${REPO}/Repo_abpe/abpe_crm/incoming/js/mod-crm-pbx.js" \
          "${CRM_STATIC}/js/mod-crm-pbx.js"

echo ""
echo "--- Templates ---"
copy_file "${REPO}/Repo_abpe/abpe_crm/incoming/templates/abpe_crm/base.html" \
          "${CRM_TEMPLATES}/base.html"
copy_file "${REPO}/Repo_abpe/abpe_crm/incoming/templates/abpe_crm/components/header.html" \
          "${CRM_TEMPLATES}/components/header.html"

echo ""
echo "--- Verifikation ---"
if grep -q "timezoneManager" "${CRM_STATIC}/js/core-timezone.js"; then
  echo "OK: core-timezone.js auf Live"
else
  echo "FEHLER: core-timezone.js unvollständig" >&2
  exit 1
fi
if grep -q "timezoneManager.fromLocalInput" "${CRM_STATIC}/js/mod-crm-pbx.js"; then
  echo "OK: mod-crm-pbx.js nutzt timezoneManager"
else
  echo "WARN: mod-crm-pbx.js evtl. ohne Timezone-Wiring" >&2
fi
if grep -q "settings-timezone" "${CRM_TEMPLATES}/components/header.html"; then
  echo "OK: header.html mit Zeitzone-Dropdown"
else
  echo "FEHLER: header.html ohne Zeitzone-Dropdown" >&2
  exit 1
fi

echo ""
echo "Fertig (Frontend). Danach:"
echo "  python ${REPO}/Repo_abpe/abpe_crm/incoming/patches/apply_user_timezone.py"
echo "  cd $BACKEND && python manage.py makemigrations abpe_crm --name crmusersettings_timezone"
echo "  python manage.py migrate abpe_crm --noinput"
echo "  python manage.py collectstatic --noinput"
echo "  supervisorctl restart abpe-django"
