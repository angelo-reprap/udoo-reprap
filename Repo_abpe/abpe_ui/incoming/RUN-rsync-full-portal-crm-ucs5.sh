#!/bin/bash
# SYNC Live → Staging → Git — Portal (abpe_ui) + CRM (abpe_crm) KOMPLETT
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/portal-i18n-phase1-bf44
#   git show origin/cursor/portal-i18n-phase1-bf44:Repo_abpe/abpe_ui/incoming/RUN-rsync-full-portal-crm-ucs5.sh | bash
#
# Nur Report (kein Kopieren):
#   DRY_RUN=1 git show origin/cursor/portal-i18n-phase1-bf44:.../RUN-rsync-full-portal-crm-ucs5.sh | bash
#
# Mit Commit+Push:
#   AUTO_COMMIT=1 git show origin/cursor/portal-i18n-phase1-bf44:.../RUN-rsync-full-portal-crm-ucs5.sh | bash

set -euo pipefail

BACKEND="${ABPE_BACKEND:-/opt/abpe/backend}"
STAGING="${STAGING:-/mnt/public/Repo_abpe}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
DRY_RUN="${DRY_RUN:-0}"
AUTO_COMMIT="${AUTO_COMMIT:-0}"
BR="${BR:-cursor/portal-i18n-phase1-bf44}"

copy_live() {
  local live_rel="$1" stag_rel="$2"
  local live="$BACKEND/$live_rel"
  local dest="$STAGING/$stag_rel"
  if [[ ! -f "$live" ]]; then
    echo "SKIP  fehlt: $live_rel"
    return 0
  fi
  if [[ "$DRY_RUN" == "1" ]]; then
    if [[ -f "$dest" ]] && cmp -s "$live" "$dest"; then
      echo "GLEICH $stag_rel"
    else
      echo "DIFF  $stag_rel"
    fi
    return 0
  fi
  mkdir -p "$(dirname "$dest")"
  cp -a "$live" "$dest"
  echo "OK    $stag_rel"
}

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

echo "=== RUN-rsync-full-portal-crm-ucs5 ==="
echo "BACKEND=$BACKEND"
echo "STAGING=$STAGING"
echo "REPO=$REPO"
echo "DRY_RUN=$DRY_RUN  AUTO_COMMIT=$AUTO_COMMIT"
echo ""

# ── Portal: Shell-Templates (flach) ──────────────────────────────────────────
echo "=== Portal Templates ==="
for f in base.html login.html footer.html help_modal.html; do
  copy_live "apps/abpe_ui/templates/abpe_ui/$f" "abpe_ui/incoming/$f"
done
for f in "$BACKEND"/apps/abpe_ui/templates/abpe_ui/components/*.html; do
  [[ -f "$f" ]] || continue
  b=$(basename "$f")
  copy_live "apps/abpe_ui/templates/abpe_ui/components/$b" "abpe_ui/incoming/$b"
done

# ── Portal: module.json + modules.json ───────────────────────────────────────
echo ""
echo "=== Portal module.json + modules.json ==="
for f in "$BACKEND"/apps/abpe_ui/templates/abpe_ui/modules/*/module.json; do
  [[ -f "$f" ]] || continue
  mod=$(basename "$(dirname "$f")")
  copy_live "apps/abpe_ui/templates/abpe_ui/modules/${mod}/module.json" \
    "abpe_ui/incoming/modules/${mod}/module.json"
done
copy_live "apps/abpe_ui/modules.json" "abpe_ui/incoming/modules.json"

# ── Portal: Modul-Templates (email_studio → email_studio/incoming) ───────────
echo ""
echo "=== Portal Modul-Templates ==="
ES_LIVE="$BACKEND/apps/abpe_ui/templates/abpe_ui/modules/email_studio"
if [[ -d "$ES_LIVE" ]]; then
  rsync_dir "$ES_LIVE" "$STAGING/email_studio/incoming" "email_studio/templates" --exclude=module.json
else
  echo "SKIP  email_studio/templates"
fi

for mod_dir in "$BACKEND"/apps/abpe_ui/templates/abpe_ui/modules/*/; do
  [[ -d "$mod_dir" ]] || continue
  mod=$(basename "$mod_dir")
  [[ "$mod" == "email_studio" ]] && continue
  has_html=false
  for hf in "$mod_dir"*.html; do
    [[ -f "$hf" ]] && has_html=true && break
  done
  [[ "$has_html" == true ]] || continue
  rsync_dir "$mod_dir" "$STAGING/abpe_ui/incoming/modules/${mod}" "modules/${mod}/templates" \
    --exclude=module.json
done

# ── Portal: JS core (flach) ──────────────────────────────────────────────────
echo ""
echo "=== Portal JS core ==="
for f in "$BACKEND"/apps/abpe_ui/static/abpe_ui/js/core/*.js; do
  [[ -f "$f" ]] || continue
  b=$(basename "$f")
  copy_live "apps/abpe_ui/static/abpe_ui/js/core/$b" "abpe_ui/incoming/$b"
done
for f in "$BACKEND"/apps/abpe_ui/static/abpe_ui/js/*.js; do
  [[ -f "$f" ]] || continue
  b=$(basename "$f")
  copy_live "apps/abpe_ui/static/abpe_ui/js/$b" "abpe_ui/incoming/$b"
done

# ── Portal: CSS core + mod (flach) ───────────────────────────────────────────
echo ""
echo "=== Portal CSS ==="
for f in "$BACKEND"/apps/abpe_ui/static/abpe_ui/css/core/*.css; do
  [[ -f "$f" ]] || continue
  b=$(basename "$f")
  copy_live "apps/abpe_ui/static/abpe_ui/css/core/$b" "abpe_ui/incoming/$b"
done
for f in "$BACKEND"/apps/abpe_ui/static/abpe_ui/css/mod/*.css; do
  [[ -f "$f" ]] || continue
  b=$(basename "$f")
  copy_live "apps/abpe_ui/static/abpe_ui/css/mod/$b" "abpe_ui/incoming/$b"
done
for f in "$BACKEND"/apps/abpe_ui/static/abpe_ui/css/*.css; do
  [[ -f "$f" ]] || continue
  b=$(basename "$f")
  copy_live "apps/abpe_ui/static/abpe_ui/css/$b" "abpe_ui/incoming/$b"
done

# ── Portal: i18n (alle Sprachen) ─────────────────────────────────────────────
echo ""
echo "=== Portal i18n (alle Sprachen) ==="
rsync_dir "$BACKEND/apps/abpe_ui/static/abpe_ui/i18n" \
  "$STAGING/abpe_ui/incoming/i18n" "abpe_ui/i18n" --delete

# ── Portal: bin + api + Python ───────────────────────────────────────────────
echo ""
echo "=== Portal bin / api / Python ==="
for f in i18n_translator.py i18n_validate.py module_scanner.py; do
  copy_live "apps/abpe_ui/bin/$f" "abpe_ui/incoming/$f"
done
for f in "$BACKEND"/apps/abpe_ui/api/components/*.py; do
  [[ -f "$f" ]] || continue
  b=$(basename "$f")
  copy_live "apps/abpe_ui/api/components/$b" "abpe_ui/incoming/api_components/$b"
done
for f in views.py urls.py; do
  copy_live "apps/abpe_ui/$f" "abpe_ui/incoming/$f"
done

# ── CRM: Templates (flach + Baum) ────────────────────────────────────────────
echo ""
echo "=== CRM Templates ==="
for f in "$BACKEND"/apps/abpe_crm/templates/abpe_crm/*.html; do
  [[ -f "$f" ]] || continue
  b=$(basename "$f")
  copy_live "apps/abpe_crm/templates/abpe_crm/$b" "abpe_crm/incoming/$b"
done
for f in "$BACKEND"/apps/abpe_crm/templates/abpe_crm/components/*.html; do
  [[ -f "$f" ]] || continue
  b=$(basename "$f")
  copy_live "apps/abpe_crm/templates/abpe_crm/components/$b" "abpe_crm/incoming/$b"
done
rsync_dir "$BACKEND/apps/abpe_crm/templates/abpe_crm" \
  "$STAGING/abpe_crm/incoming/templates/abpe_crm" "crm/templates-tree"

# ── CRM: JS (alle) ───────────────────────────────────────────────────────────
echo ""
echo "=== CRM JS ==="
rsync_dir "$BACKEND/apps/abpe_crm/static/abpe_crm/js" \
  "$STAGING/abpe_crm/incoming/js" "crm/js" --delete
for f in "$BACKEND"/apps/abpe_crm/static/abpe_crm/js/*.js; do
  [[ -f "$f" ]] || continue
  b=$(basename "$f")
  copy_live "apps/abpe_crm/static/abpe_crm/js/$b" "abpe_crm/incoming/$b"
done

# ── CRM: i18n (alle Sprachen) ────────────────────────────────────────────────
echo ""
echo "=== CRM i18n (alle Sprachen) ==="
rsync_dir "$BACKEND/apps/abpe_crm/static/abpe_crm/i18n" \
  "$STAGING/abpe_crm/incoming/i18n" "crm/i18n" --delete

# ── CRM: Python ──────────────────────────────────────────────────────────────
echo ""
echo "=== CRM Python ==="
for f in views.py urls.py models.py reporting_api.py; do
  copy_live "apps/abpe_crm/$f" "abpe_crm/incoming/$f"
done
for f in "$BACKEND"/apps/abpe_crm/bin/*.py; do
  [[ -f "$f" ]] || continue
  b=$(basename "$f")
  copy_live "apps/abpe_crm/bin/$b" "abpe_crm/incoming/bin/$b"
done

if [[ "$DRY_RUN" == "1" ]]; then
  echo ""
  echo "=== DRY_RUN fertig — nichts nach Git ==="
  exit 0
fi

# ── Staging → Git-Clone ──────────────────────────────────────────────────────
echo ""
echo "=== Staging → Git-Clone ==="
rsync -a \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  "$STAGING/abpe_ui/incoming/" "$REPO/Repo_abpe/abpe_ui/incoming/"
rsync -a \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  "$STAGING/abpe_crm/incoming/" "$REPO/Repo_abpe/abpe_crm/incoming/"
rsync -a \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  "$STAGING/email_studio/incoming/" "$REPO/Repo_abpe/email_studio/incoming/" 2>/dev/null || true
rm -rf "$REPO/Repo_abpe/abpe_ui/incoming/modules/opt"

echo ""
echo "=== SYNC fertig ==="
if [[ "$AUTO_COMMIT" == "1" ]]; then
  cd "$REPO"
  git add Repo_abpe/abpe_ui/incoming/ Repo_abpe/abpe_crm/incoming/ Repo_abpe/email_studio/incoming/ 2>/dev/null || true
  git add Repo_abpe/abpe_ui/incoming/ Repo_abpe/abpe_crm/incoming/
  if git diff --cached --quiet; then
    echo "Keine Änderungen — nichts zu committen."
  else
    git commit -m "Live rsync: portal + abpe_crm (full)"
    git push origin "$BR" 2>/dev/null || git push
    echo "Gepusht."
  fi
else
  echo "  cd $REPO"
  echo "  git add Repo_abpe/abpe_ui/incoming/ Repo_abpe/abpe_crm/incoming/ Repo_abpe/email_studio/incoming/"
  echo "  git status"
  echo "  git commit -m 'Live rsync: portal + abpe_crm (full)'"
  echo "  git push"
fi
