#!/usr/bin/env bash
# SYNC Live → Git — CRM Theme/Dark-Mode Iststand (CSS + JS + Templates)
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/crm-dark-mode-bf44
#   git checkout cursor/crm-dark-mode-bf44
#   git pull origin cursor/crm-dark-mode-bf44
#   bash Repo_abpe/abpe_crm/incoming/RUN-rsync-crm-theme-ucs5.sh
#
# Nur Report (kein Kopieren):
#   DRY_RUN=1 bash Repo_abpe/abpe_crm/incoming/RUN-rsync-crm-theme-ucs5.sh
#
# Mit Commit+Push:
#   AUTO_COMMIT=1 bash Repo_abpe/abpe_crm/incoming/RUN-rsync-crm-theme-ucs5.sh

set -euo pipefail

BACKEND="${ABPE_BACKEND:-/opt/abpe/backend}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
INCOMING="${REPO}/Repo_abpe/abpe_crm/incoming"
DRY_RUN="${DRY_RUN:-0}"
AUTO_COMMIT="${AUTO_COMMIT:-0}"
BR="${BR:-cursor/crm-dark-mode-bf44}"

LIVE_CRM="${BACKEND}/apps/abpe_crm"
LIVE_STATIC="${LIVE_CRM}/static/abpe_crm"
LIVE_TPL="${LIVE_CRM}/templates/abpe_crm"

rsync_dir() {
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

copy_file() {
  local live_rel="$1" dest_rel="$2"
  local live="${LIVE_CRM}/${live_rel}"
  local dest="${INCOMING}/${dest_rel}"
  if [[ ! -f "$live" ]]; then
    echo "SKIP  fehlt: $live_rel"
    return 0
  fi
  if [[ "$DRY_RUN" == "1" ]]; then
    if [[ -f "$dest" ]] && cmp -s "$live" "$dest"; then
      echo "GLEICH $dest_rel"
    else
      echo "DIFF  $dest_rel"
    fi
    return 0
  fi
  mkdir -p "$(dirname "$dest")"
  cp -a "$live" "$dest"
  echo "OK    $dest_rel"
}

echo "=== RUN-rsync-crm-theme-ucs5 ==="
echo "BACKEND=$BACKEND"
echo "REPO=$REPO"
echo "INCOMING=$INCOMING"
echo "DRY_RUN=$DRY_RUN  AUTO_COMMIT=$AUTO_COMMIT"
echo ""

# ── 1. CRM CSS (komplett — bisher nicht im Git!) ─────────────────────────────
echo "=== CRM CSS (static/abpe_crm/css) ==="
rsync_dir "$LIVE_STATIC/css" "$INCOMING/css" "crm/css" \
  --exclude='*.map'

# Softphone CSS (separater Pfad)
echo ""
echo "=== CRM Softphone CSS ==="
rsync_dir "$LIVE_STATIC/softphone/css" "$INCOMING/softphone/css" "crm/softphone/css"

# ── 2. Theme-JS + alle Modul-JS ──────────────────────────────────────────────
echo ""
echo "=== CRM JS (theme + module) ==="
rsync_dir "$LIVE_STATIC/js" "$INCOMING/js" "crm/js" \
  --exclude='*.map'

# Flache Kopien der wichtigsten JS (Deploy-Kompatibilität)
for f in core-theme.js core-language.js ui-modal.js mod-crm.js mod-crm-edit.js \
         mod-crm-kunden.js mod-crm-berater.js mod-crm-kampagne.js mod-crm-pbx.js \
         mod-edms.js mod-crm-dokumente.js mod-crm-reporting.js mod-softphone-ext.js; do
  copy_file "static/abpe_crm/js/$f" "$f"
done

# ── 3. Templates (inline styles, header toggle, base.html) ─────────────────
echo ""
echo "=== CRM Templates ==="
rsync_dir "$LIVE_TPL" "$INCOMING/templates/abpe_crm" "crm/templates" \
  --exclude='*_backup_*'

# Flache Kopien Shell-Templates
for f in base.html login.html logged_out.html footer.html help_modal.html header.html sidebar.html crm_search.html; do
  copy_file "templates/abpe_crm/$f" "$f" 2>/dev/null || \
  copy_file "templates/abpe_crm/components/$f" "$f" 2>/dev/null || true
done
[[ -f "${LIVE_TPL}/components/header.html" ]] && copy_file "templates/abpe_crm/components/header.html" "templates/abpe_crm/components/header.html"

# ── 4. Audit: hardcodierte Farben inventarisieren ────────────────────────────
if [[ "$DRY_RUN" != "1" ]]; then
  AUDIT="${INCOMING}/THEME-AUDIT.txt"
  echo ""
  echo "=== Audit → THEME-AUDIT.txt ==="
  {
    echo "# CRM Theme Audit — $(date -Iseconds)"
    echo "# Generiert von RUN-rsync-crm-theme-ucs5.sh auf $(hostname)"
    echo ""
    echo "## CSS-Dateien ($(find "$INCOMING/css" -name '*.css' 2>/dev/null | wc -l) Stück)"
    find "$INCOMING/css" -name '*.css' 2>/dev/null | sort | sed "s|$INCOMING/||"
    echo ""
    echo "## Hardcoded colors in CSS (background/color #fff white rgb)"
    grep -rn --include='*.css' -E 'background:\s*(white|#fff|#ffffff)|color:\s*#|background:\s*#' \
      "$INCOMING/css" 2>/dev/null | head -200 || echo "(keine Treffer oder css/ leer)"
    echo ""
    echo "## Hardcoded colors in JS (style/background/#fff)"
    grep -rn --include='*.js' -E '#fff|#ffffff|background:\s*white|background:\s*#f|style=.*background' \
      "$INCOMING/js" "$INCOMING"/*.js 2>/dev/null | grep -v jssip | head -200 || echo "(keine Treffer)"
    echo ""
    echo "## Hardcoded colors in HTML templates"
    grep -rn --include='*.html' -E 'background:\s*(white|#)|background-color:\s*#|style=.*#fff' \
      "$INCOMING/templates" "$INCOMING"/*.html 2>/dev/null | head -200 || echo "(keine Treffer)"
    echo ""
    echo "## var(--*) Nutzung in CSS (gut)"
    grep -rc 'var(--' "$INCOMING/css"/*.css 2>/dev/null | sort -t: -k2 -nr | head -20 || true
  } > "$AUDIT"
  echo "OK    THEME-AUDIT.txt ($(wc -l < "$AUDIT") Zeilen)"
fi

if [[ "$DRY_RUN" == "1" ]]; then
  echo ""
  echo "=== DRY_RUN fertig — nichts geschrieben ==="
  exit 0
fi

echo ""
echo "=== SYNC fertig ==="
echo "  CSS:       $INCOMING/css/"
echo "  JS:        $INCOMING/js/"
echo "  Templates: $INCOMING/templates/abpe_crm/"
echo "  Audit:     $INCOMING/THEME-AUDIT.txt"

if [[ "$AUTO_COMMIT" == "1" ]]; then
  cd "$REPO"
  git add Repo_abpe/abpe_crm/incoming/css/ \
          Repo_abpe/abpe_crm/incoming/softphone/ \
          Repo_abpe/abpe_crm/incoming/js/ \
          Repo_abpe/abpe_crm/incoming/templates/ \
          Repo_abpe/abpe_crm/incoming/THEME-AUDIT.txt \
          Repo_abpe/abpe_crm/incoming/*.js \
          Repo_abpe/abpe_crm/incoming/*.html 2>/dev/null || true
  git add Repo_abpe/abpe_crm/incoming/RUN-rsync-crm-theme-ucs5.sh \
          Repo_abpe/abpe_crm/incoming/THEME-CRM-PLAN.md
  if git diff --cached --quiet; then
    echo "Keine Änderungen — nichts zu committen."
  else
    git commit -m "Live rsync: CRM theme/CSS Iststand + audit"
    git push origin "$BR"
    echo "Gepusht nach $BR"
  fi
else
  echo ""
  echo "Manuell committen:"
  echo "  cd $REPO"
  echo "  git add Repo_abpe/abpe_crm/incoming/css/ Repo_abpe/abpe_crm/incoming/THEME-AUDIT.txt ..."
  echo "  git commit -m 'Live rsync: CRM theme/CSS Iststand'"
  echo "  git push origin $BR"
fi
