#!/usr/bin/env bash
# Exportiert abpe_meetme + abpe_scheduler von ucs5 ins Repo (für Cloud-Agent / Git).
#
# Auf ucs5 als root:
#   cd /mnt/public/udoo-reprap
#   git pull
#   bash scripts/export-meetme-backend.sh
#   git add Repo_abpe/abpe_meetme Repo_abpe/abpe_scheduler scripts/
#   git commit -m "Export: MeetMe + Scheduler Backend von ucs5"
#   git push
#
# Optional — direkt ins Git-Working-Tree (Standard auf ucs5):
#   UDOO_REPO=/mnt/public/udoo-reprap bash scripts/export-meetme-backend.sh
#
# Nur anzeigen:
#   DRY_RUN=1 bash scripts/export-meetme-backend.sh

set -euo pipefail

BACKEND="${ABPE_BACKEND:-/opt/abpe/backend}"
STAGING="${REPO_ABPE_STAGING:-/mnt/public/Repo_abpe}"
UDOO_REPO="${UDOO_REPO:-/mnt/public/udoo-reprap}"
DRY_RUN="${DRY_RUN:-0}"

APPS=(abpe_meetme abpe_scheduler)

if [[ ! -d "$BACKEND/apps" ]]; then
  echo "Fehler: Backend nicht gefunden: $BACKEND/apps" >&2
  exit 1
fi

export_app() {
  local app="$1"
  local src="${BACKEND}/apps/${app}"
  local dest_staging="${STAGING}/${app}/incoming"
  local dest_git="${UDOO_REPO}/Repo_abpe/${app}/incoming"

  if [[ ! -d "$src" ]]; then
    echo "WARN: App fehlt auf ucs5 — $src"
    return 0
  fi

  echo ""
  echo "=== Export $app ==="
  echo "Quelle:  $src"
  echo "Staging: $dest_staging"

  if [[ "$DRY_RUN" == "1" ]]; then
    echo "--- DRY RUN (würde kopieren) ---"
    find "$src" -type f \( -name '*.py' -o -name '*.json' \) ! -path '*/__pycache__/*' | sort
    return 0
  fi

  mkdir -p "$dest_staging"
  rsync -a --delete \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --include '*/' \
    --include '*.py' \
    --include 'migrations/*.py' \
    --exclude '*' \
    "$src/" "$dest_staging/"

  local count
  count=$(find "$dest_staging" -type f -name '*.py' | wc -l | tr -d ' ')
  echo "OK: $count Python-Dateien -> $dest_staging"

  if [[ -d "$UDOO_REPO/Repo_abpe" ]]; then
    mkdir -p "$dest_git"
    rsync -a --delete \
      --exclude '__pycache__/' \
      --exclude '*.pyc' \
      "$dest_staging/" "$dest_git/"
    echo "OK: Git-Spiegel -> $dest_git"
  else
    echo "Hinweis: UDOO_REPO nicht gefunden ($UDOO_REPO) — nur Staging aktualisiert"
  fi

  find "$dest_staging" -type f -name '*.py' | sort > "${STAGING}/${app}/FILELIST.txt"
  if [[ -d "$UDOO_REPO/Repo_abpe" ]]; then
    cp "${STAGING}/${app}/FILELIST.txt" "${UDOO_REPO}/Repo_abpe/${app}/FILELIST.txt"
  fi
}

write_manifest() {
  local manifest="${UDOO_REPO}/Repo_abpe/abpe_meetme/EXPORT-MANIFEST.txt"
  if [[ "$DRY_RUN" == "1" ]]; then
    return 0
  fi
  if [[ ! -d "$UDOO_REPO/Repo_abpe" ]]; then
    return 0
  fi
  {
    echo "MeetMe/Scheduler Export — $(date -Iseconds)"
    echo "Backend: $BACKEND"
    for app in "${APPS[@]}"; do
      echo ""
      echo "[$app]"
      if [[ -f "${STAGING}/${app}/FILELIST.txt" ]]; then
        cat "${STAGING}/${app}/FILELIST.txt"
      fi
    done
  } > "$manifest"
  echo "OK: Manifest -> $manifest"
}

for app in "${APPS[@]}"; do
  export_app "$app"
done

write_manifest

echo ""
echo "=== Export fertig ==="
for app in "${APPS[@]}"; do
  dir="${STAGING}/${app}/incoming"
  if [[ -d "$dir" ]]; then
    count=$(find "$dir" -type f -name '*.py' 2>/dev/null | wc -l | tr -d ' ')
    echo "  ${app}: ${count} .py — ${dir}"
  fi
done

cat <<'EOF'

Nächster Schritt (auf ucs5):
  cd /mnt/public/udoo-reprap
  git status
  git add Repo_abpe/abpe_meetme Repo_abpe/abpe_scheduler scripts/export-meetme-backend.sh scripts/export-to-repo.sh
  git commit -m "Export: MeetMe + Scheduler Backend von ucs5"
  git push

Dann Cloud Agent: Konferenz Einladung + Erinnerung End-to-End testen und fixen.
EOF
