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
echo "--- i18n Zeitzonen (418 Zonen × 14 Sprachen) ---"
I18N_SRC="${REPO}/Repo_abpe/abpe_crm/incoming/i18n"
I18N_DEST="${BACKEND}/apps/abpe_crm/static/abpe_crm/i18n"
mkdir -p "$I18N_DEST"
cp -a "${I18N_SRC}/timezone.base.json" "${I18N_DEST}/"
for lang in de en fr es it pt nl pl ru tr ar zh ja ko; do
  mkdir -p "${I18N_DEST}/${lang}"
  cp -a "${I18N_SRC}/${lang}/timezone.json" "${I18N_DEST}/${lang}/"
done
echo "OK: timezone.base.json + 14× timezone.json → ${I18N_DEST}"

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
if grep -q "settings-timezone-search" "${CRM_TEMPLATES}/components/header.html"; then
  echo "OK: header.html mit kaskadierten Zeitzonen-Dropdowns + Suche"
else
  echo "FEHLER: header.html ohne Zeitzonen-UI" >&2
  exit 1
fi
if [[ -f "${I18N_DEST}/de/timezone.json" ]] && [[ -f "${I18N_DEST}/timezone.base.json" ]]; then
  echo "OK: i18n/timezone.json deployed ($(wc -l < "${I18N_DEST}/de/timezone.json") Zeilen de)"
else
  echo "FEHLER: timezone i18n fehlt" >&2
  exit 1
fi

echo ""
echo "Fertig (Frontend). Danach:"
echo "  python ${REPO}/Repo_abpe/abpe_crm/incoming/patches/apply_user_timezone.py"
echo "  cd $BACKEND && python manage.py makemigrations abpe_crm --name crmusersettings_timezone"
echo "  python manage.py migrate abpe_crm --noinput"
echo "  python manage.py collectstatic --noinput"
echo "  supervisorctl restart abpe-django"
