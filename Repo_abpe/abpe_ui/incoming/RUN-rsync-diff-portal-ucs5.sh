#!/bin/bash
# SYNC Live → Staging → Git — nur geänderte Dateien (MD5/checksum)
# Portal Phase 1: Shell, Sprach-API, i18n-Tools, hu/
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/portal-i18n-phase1-bf44
#   git show origin/cursor/portal-i18n-phase1-bf44:Repo_abpe/abpe_ui/incoming/RUN-rsync-diff-portal-ucs5.sh | bash
#
# Nur Report (kein Kopieren):
#   DRY_RUN=1 git show origin/cursor/portal-i18n-phase1-bf44:.../RUN-rsync-diff-portal-ucs5.sh | bash

set -euo pipefail

BACKEND="${ABPE_BACKEND:-/opt/abpe/backend}"
STAGING="${STAGING:-/mnt/public/Repo_abpe}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
DRY_RUN="${DRY_RUN:-0}"

# live_rel|staging_rel unter Repo_abpe/
FILES=(
  "apps/abpe_ui/templates/abpe_ui/base.html|abpe_ui/incoming/base.html"
  "apps/abpe_ui/templates/abpe_ui/components/header.html|abpe_ui/incoming/header.html"
  "apps/abpe_ui/templates/abpe_ui/components/sidebar.html|abpe_ui/incoming/sidebar.html"
  "apps/abpe_ui/templates/abpe_ui/components/_nav_link.html|abpe_ui/incoming/_nav_link.html"
  "apps/abpe_ui/static/abpe_ui/js/core/core-language.js|abpe_ui/incoming/core-language.js"
  "apps/abpe_ui/static/abpe_ui/js/core/core-lang-dropdown.js|abpe_ui/incoming/core-lang-dropdown.js"
  "apps/abpe_ui/bin/i18n_translator.py|abpe_ui/incoming/i18n_translator.py"
  "apps/abpe_ui/bin/i18n_validate.py|abpe_ui/incoming/i18n_validate.py"
  "apps/abpe_ui/api/components/set_language.py|abpe_ui/incoming/api_components/set_language.py"
  "apps/abpe_ui/api/components/available_languages.py|abpe_ui/incoming/api_components/available_languages.py"
  "apps/abpe_ui/api/components/language_manager.py|abpe_ui/incoming/api_components/language_manager.py"
  "apps/abpe_ui/views.py|abpe_ui/incoming/views.py"
)

md5_of() {
  md5sum "$1" 2>/dev/null | awk '{print $1}'
}

copy_if_diff() {
  local live="$1" dest="$2" label="$3"
  if [[ ! -f "$live" ]]; then
    echo "SKIP  fehlt Live: $label"
    return 0
  fi
  local live_md5 dest_md5=""
  live_md5=$(md5_of "$live")
  if [[ -f "$dest" ]]; then
    dest_md5=$(md5_of "$dest")
    if [[ "$live_md5" == "$dest_md5" ]]; then
      echo "GLEICH $label  md5=$live_md5"
      return 0
    fi
    echo "DIFF  $label  live=$live_md5 staging=$dest_md5"
  else
    echo "NEU   $label  live=$live_md5 (staging fehlt)"
  fi
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "      → würde kopieren (DRY_RUN)"
    return 0
  fi
  mkdir -p "$(dirname "$dest")"
  cp -a "$live" "$dest"
  echo "      → kopiert"
}

echo "=== Portal Datei-Sync (MD5-Diff) Live → $STAGING ==="
echo "DRY_RUN=$DRY_RUN"
echo ""

changed=0
equal=0
skipped=0

for entry in "${FILES[@]}"; do
  live_rel="${entry%%|*}"
  stag_rel="${entry##*|}"
  live="$BACKEND/$live_rel"
  dest="$STAGING/$stag_rel"
  before="$dest"
  copy_if_diff "$live" "$dest" "$stag_rel"
  if [[ ! -f "$live" ]]; then
    ((skipped++)) || true
  elif [[ -f "$before" ]] && [[ -f "$live" ]] && [[ "$(md5_of "$before")" == "$(md5_of "$live")" ]]; then
    ((equal++)) || true
  elif [[ -f "$live" ]]; then
    if [[ "$DRY_RUN" != "1" ]]; then
      ((changed++)) || true
    elif [[ ! -f "$before" ]] || [[ "$(md5_of "$before" 2>/dev/null)" != "$(md5_of "$live")" ]]; then
      ((changed++)) || true
    fi
  fi
done

echo ""
echo "=== module.json (MD5 je Modul) ==="
for f in "$BACKEND"/apps/abpe_ui/templates/abpe_ui/modules/*/module.json; do
  [[ -f "$f" ]] || continue
  mod=$(basename "$(dirname "$f")")
  dest="$STAGING/abpe_ui/incoming/modules/${mod}/module.json"
  copy_if_diff "$f" "$dest" "modules/${mod}/module.json"
done

echo ""
echo "=== i18n Portal (rsync --checksum, nur Unterschiede) ==="
for lang in de en ar zh hu; do
  src="$BACKEND/apps/abpe_ui/static/abpe_ui/i18n/$lang"
  dest="$STAGING/abpe_ui/incoming/i18n/$lang"
  if [[ ! -d "$src" ]]; then
    echo "SKIP  i18n/$lang (Live fehlt)"
    continue
  fi
  mkdir -p "$dest"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "--- i18n/$lang (dry-run) ---"
    rsync -ani --checksum "$src/" "$dest/" | grep -E '^[<>ch]' || echo "GLEICH i18n/$lang"
  else
    echo "--- i18n/$lang ---"
    rsync -a --checksum --itemize-changes "$src/" "$dest/" | grep -E '^[<>ch]' || echo "GLEICH i18n/$lang"
  fi
done

if [[ "$DRY_RUN" == "1" ]]; then
  echo ""
  echo "=== DRY_RUN fertig — nichts kopiert, nichts nach Git ==="
  exit 0
fi

echo ""
echo "=== Staging → Git-Clone (rsync, nur Unterschiede) ==="
rsync -a --checksum --itemize-changes \
  "$STAGING/abpe_ui/incoming/" "$REPO/Repo_abpe/abpe_ui/incoming/" \
  | grep -E '^[<>ch]' || echo "GLEICH Repo_abpe/abpe_ui/incoming/"
rm -rf "$REPO/Repo_abpe/abpe_ui/incoming/modules/opt"

echo ""
echo "=== Zusammenfassung ==="
echo "  Einzeldateien geändert/neu: $changed"
echo "  Nächster Schritt:"
echo "    cd $REPO"
echo "    git add Repo_abpe/abpe_ui/incoming/"
echo "    git status"
echo "    git commit -m 'Live rsync-diff: portal phase1'"
echo "    git push"
