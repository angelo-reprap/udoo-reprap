#!/usr/bin/env bash
# Vollständiger CRM-Deploy: Git incoming/ → Live (ucs5)
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/crm-dark-mode-bf44
#   git checkout cursor/crm-dark-mode-bf44
#   git pull origin cursor/crm-dark-mode-bf44
#   bash Repo_abpe/abpe_crm/incoming/RUN-deploy-crm-full-ucs5.sh
#   cd /opt/abpe/backend && python manage.py collectstatic --noinput
#   supervisorctl restart abpe-django
#
# Nur anzeigen (kein Kopieren):
#   DRY_RUN=1 bash Repo_abpe/abpe_crm/incoming/RUN-deploy-crm-full-ucs5.sh

set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
INCOMING="$(cd "$(dirname "$0")" && pwd)"
STATIC="${BACKEND}/apps/abpe_crm/static/abpe_crm"
TPL="${BACKEND}/apps/abpe_crm/templates/abpe_crm"
ARCHIV="${BACKEND}/Archiv"
DRY_RUN="${DRY_RUN:-0}"

rsync_to_live() {
  local src="$1" dest="$2" label="$3"
  shift 3
  local -a extra=("$@")
  if [[ ! -d "$src" ]]; then
    echo "SKIP  fehlt: $label ($src)"
    return 0
  fi
  mkdir -p "$dest"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "--- DRY $label ---"
    rsync -ani --checksum "${extra[@]}" "$src/" "$dest/" | grep -E '^[<>ch*]' || echo "GLEICH $label"
    return 0
  fi
  echo "--- $label ---"
  rsync -a --checksum --itemize-changes "${extra[@]}" "$src/" "$dest/" \
    | grep -E '^[<>ch*]' || echo "GLEICH $label"
}

copy_one() {
  local src_rel="$1" dest_rel="$2"
  local src="${INCOMING}/${src_rel}"
  local dest="${BACKEND}/${dest_rel}"
  if [[ ! -f "$src" ]]; then
    echo "SKIP  fehlt: $src_rel"
    return 0
  fi
  if [[ "$DRY_RUN" == "1" ]]; then
    if [[ -f "$dest" ]] && cmp -s "$src" "$dest"; then
      echo "GLEICH $dest_rel"
    else
      echo "DIFF  $dest_rel"
    fi
    return 0
  fi
  mkdir -p "$(dirname "$dest")"
  cp -a "$src" "$dest"
  echo "OK    $dest_rel"
}

echo "=== CRM Full Deploy (Git → Live) ==="
echo "INCOMING=$INCOMING"
echo "BACKEND=$BACKEND"
echo "DRY_RUN=$DRY_RUN"
echo ""

# Flache JS-Kopien aus js/ aktualisieren (Deploy-Kompatibilität)
if [[ "$DRY_RUN" != "1" ]]; then
  echo "=== Flat JS sync (js/ → incoming/) ==="
  for f in core-theme.js core-language.js ui-modal.js mod-crm.js mod-crm-edit.js \
           mod-crm-kunden.js mod-crm-berater.js mod-crm-kampagne.js mod-crm-pbx.js \
           mod-edms.js mod-crm-dokumente.js mod-crm-reporting.js mod-softphone-ext.js; do
    [[ -f "${INCOMING}/js/$f" ]] && cp -a "${INCOMING}/js/$f" "${INCOMING}/$f" && echo "OK    $f"
  done
  echo ""
fi

# CSS (komplett)
rsync_to_live "${INCOMING}/css" "${STATIC}/css" "crm/css" --exclude='*.map' --exclude='*.before_restore'

# JS (komplett)
rsync_to_live "${INCOMING}/js" "${STATIC}/js" "crm/js" \
  --exclude='*.map' \
  --exclude='*.before_restore' \
  --exclude='*.bak*' \
  --exclude='core-language_backup_*'

# Softphone CSS
rsync_to_live "${INCOMING}/softphone/css" "${STATIC}/softphone/css" "crm/softphone/css" \
  --exclude='*.before_restore'

# Templates (komplett, ohne Backups)
rsync_to_live "${INCOMING}/templates/abpe_crm" "${TPL}" "crm/templates" \
  --exclude='*_backup_*' \
  --exclude='*.before_restore'

# Alte Backup-Dateien auf Live entfernen
if [[ "$DRY_RUN" != "1" ]]; then
  echo ""
  echo "=== Alte Backups auf Live entfernen ==="
  find "${STATIC}" "${TPL}" -name '*.before_restore' -delete 2>/dev/null || true
  find "${STATIC}/js" -name '*.bak*' -delete 2>/dev/null || true
  echo "OK    .before_restore / .bak entfernt"
fi

# Optional: Archiv-Backup vor Deploy
if [[ "${BACKUP:-0}" == "1" && "$DRY_RUN" != "1" && -x "${ARCHIV}/backup_restore.py" ]]; then
  echo ""
  echo "=== Archiv-Backup ==="
  NOTE="${NOTE:-vor crm-full-deploy}"
  while IFS= read -r rel; do
    [[ -f "${BACKEND}/${rel}" ]] && python3 "${ARCHIV}/backup_restore.py" -save "${rel}" -m "${NOTE}" || true
  done < <(find "${INCOMING}/css" "${INCOMING}/js" -type f \( -name '*.css' -o -name '*.js' \) \
    ! -name '*.bak*' ! -name '*backup*' \
    | sed "s|^${INCOMING}/css/|apps/abpe_crm/static/abpe_crm/css/|" \
    | sed "s|^${INCOMING}/js/|apps/abpe_crm/static/abpe_crm/js/|")
fi

if [[ "$DRY_RUN" == "1" ]]; then
  echo ""
  echo "=== DRY_RUN fertig — nichts geschrieben ==="
  exit 0
fi

echo ""
echo "=== Deploy fertig ==="
echo "  CSS:       ${STATIC}/css/  ($(find "${INCOMING}/css" -name '*.css' | wc -l) Dateien)"
echo "  JS:        ${STATIC}/js/   ($(find "${INCOMING}/js" -name '*.js' ! -name '*backup*' ! -name '*.bak*' | wc -l) Dateien)"
echo "  Templates: ${TPL}/"
echo ""
echo "Nächste Schritte:"
echo "  cd ${BACKEND} && python manage.py collectstatic --noinput"
echo "  supervisorctl restart abpe-django"
