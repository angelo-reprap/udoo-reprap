#!/usr/bin/env bash
# Kopiert geänderte Live-Dateien von ucs5 nach /mnt/public/Repo_abpe/<modul>/incoming/
#
# Verwendung:
#   export-to-repo.sh <modul> <quell-datei> [weitere-quellen...]
#   export-to-repo.sh <modul> --from-backend <rel-pfad-unter-apps/> [weitere...]
#
# Beispiele:
#   export-to-repo.sh abpe_reporting \
#     /opt/abpe/backend/apps/abpe_crm/static/abpe_crm/js/mod-crm-reporting.js
#
#   export-to-repo.sh abpe_crm --from-backend \
#     abpe_crm/static/abpe_crm/js/mod-crm-reporting.js
#
# Umgebungsvariablen (optional):
#   ABPE_BACKEND=/opt/abpe/backend
#   REPO_ABPE_STAGING=/mnt/public/Repo_abpe

set -euo pipefail

BACKEND_ROOT="${ABPE_BACKEND:-/opt/abpe/backend}"
STAGING_ROOT="${REPO_ABPE_STAGING:-/mnt/public/Repo_abpe}"

usage() {
  cat <<'EOF'
export-to-repo.sh — Live-Dateien nach Repo_abpe-Staging kopieren

Verwendung:
  export-to-repo.sh <modul> <quell-datei> [weitere-quellen...]
  export-to-repo.sh <modul> --from-backend <rel-pfad-unter-apps/> [weitere...]

Beispiele:
  export-to-repo.sh abpe_reporting \
    /opt/abpe/backend/apps/abpe_crm/static/abpe_crm/js/mod-crm-reporting.js

  export-to-repo.sh abpe_crm --from-backend \
    abpe_crm/static/abpe_crm/js/mod-crm-reporting.js

Zielverzeichnis:
  /mnt/public/Repo_abpe/<modul>/incoming/

Git-Spiegel in udoo-reprap:
  Repo_abpe/<modul>/incoming/
EOF
}

if [[ $# -lt 2 ]]; then
  usage
  exit 1
fi

module="$1"
shift

if [[ ! "$module" =~ ^[a-z][a-z0-9_]*$ ]]; then
  echo "Fehler: Modulname ungültig (nur Kleinbuchstaben, Ziffern, Unterstrich): $module" >&2
  exit 1
fi

dest_dir="${STAGING_ROOT}/${module}/incoming"
mkdir -p "$dest_dir"

copy_file() {
  local src="$1"
  local base
  base="$(basename "$src")"

  if [[ ! -e "$src" ]]; then
    echo "Fehler: Quelle existiert nicht: $src" >&2
    exit 1
  fi

  cp -a "$src" "${dest_dir}/${base}"
  echo "OK: ${src} -> ${dest_dir}/${base}"
}

if [[ "$1" == "--from-backend" ]]; then
  shift
  if [[ $# -eq 0 ]]; then
    echo "Fehler: --from-backend braucht mindestens einen Relativpfad unter apps/" >&2
    exit 1
  fi
  for rel in "$@"; do
    rel="${rel#apps/}"
    copy_file "${BACKEND_ROOT}/apps/${rel}"
  done
else
  for src in "$@"; do
    copy_file "$src"
  done
fi

echo ""
echo "Staging fertig: ${dest_dir}"
echo "Nächster Schritt: Dateien nach Repo_abpe/${module}/incoming/ im udoo-reprap-Clone legen und pushen."
echo "Cloud Agent: \"Bitte Repo_abpe/${module}/incoming/ analysieren …\""
