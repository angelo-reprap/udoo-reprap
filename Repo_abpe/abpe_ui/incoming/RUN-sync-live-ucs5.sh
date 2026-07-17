#!/bin/bash
# SYNC Live → Repo (ucs5) — Compose + i18n + alle relevanten Dateien
# Siehe Repo_abpe/WORKFLOW.md — Schritt 1 ONLY. Agent analysiert erst NACH push.
#
# Auf JEDEM Branch:
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/email-studio-undo-i18n-bf44
#   git show origin/cursor/email-studio-undo-i18n-bf44:Repo_abpe/abpe_ui/incoming/RUN-sync-live-ucs5.sh | bash
#
# Danach:
#   cd /mnt/public/udoo-reprap
#   git add Repo_abpe/
#   git status
#   git commit -m "Live sync: compose + i18n"
#   git push
#   → Agent: "Sync ist gepusht"

set -euo pipefail

BACKEND="${ABPE_BACKEND:-/opt/abpe/backend}"
EXPORT="${ABPE_EXPORT_SH:-/opt/abpe/scripts/export-to-repo.sh}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
STAGING="/mnt/public/Repo_abpe"

if [[ ! -x "$EXPORT" ]]; then
  echo "FEHLER: $EXPORT nicht gefunden." >&2
  exit 1
fi

echo "=== Portal Shell + JS ==="
"$EXPORT" abpe_ui \
  "$BACKEND/apps/abpe_ui/templates/abpe_ui/base.html" \
  "$BACKEND/apps/abpe_ui/templates/abpe_ui/components/header.html" \
  "$BACKEND/apps/abpe_ui/templates/abpe_ui/components/sidebar.html" \
  "$BACKEND/apps/abpe_ui/templates/abpe_ui/components/_nav_link.html" \
  "$BACKEND/apps/abpe_ui/static/abpe_ui/js/core/core-language.js" \
  "$BACKEND/apps/abpe_ui/static/abpe_ui/js/core/core-lang-dropdown.js" \
  "$BACKEND/apps/abpe_ui/bin/i18n_translator.py" \
  "$BACKEND/apps/abpe_ui/bin/i18n_validate.py"

echo ""
echo "=== CRM Shell + JS ==="
"$EXPORT" abpe_crm \
  "$BACKEND/apps/abpe_crm/templates/abpe_crm/base.html" \
  "$BACKEND/apps/abpe_crm/templates/abpe_crm/components/header.html" \
  "$BACKEND/apps/abpe_crm/static/abpe_crm/js/core-language.js" \
  "$BACKEND/apps/abpe_crm/static/abpe_crm/js/core-crm-lang-dropdown.js"

echo ""
echo "=== Compose (KRITISCH — welche Scripts werden geladen?) ==="
if [[ -f "$BACKEND/apps/abpe_crm/templates/abpe_crm/email_compose.html" ]]; then
  "$EXPORT" abpe_crm "$BACKEND/apps/abpe_crm/templates/abpe_crm/email_compose.html"
else
  echo "WARN: email_compose.html fehlt auf Live"
fi

echo ""
echo "=== Email Studio Templates ==="
for f in \
  "$BACKEND/apps/abpe_ui/templates/abpe_ui/modules/email_studio/base.html" \
  "$BACKEND/apps/abpe_email_studio/templates/email_studio/base.html" \
  "$BACKEND/apps/abpe_ui/templates/abpe_ui/modules/email_studio/studio.html" \
  "$BACKEND/apps/abpe_email_studio/templates/email_studio/studio.html"
do
  if [[ -f "$f" ]]; then
    "$EXPORT" email_studio "$f"
  fi
done

echo ""
echo "=== module.json (flach) ==="
for f in "$BACKEND"/apps/abpe_ui/templates/abpe_ui/modules/*/module.json; do
  mod=$(basename "$(dirname "$f")")
  mkdir -p "$STAGING/abpe_ui/incoming/modules/${mod}"
  cp -a "$f" "$STAGING/abpe_ui/incoming/modules/${mod}/module.json"
  echo "OK: module.json → ${mod}"
done

echo ""
echo "=== i18n Sprachordner (Portal) ==="
for lang in de en ar zh hu; do
  src="$BACKEND/apps/abpe_ui/static/abpe_ui/i18n/$lang"
  if [[ -d "$src" ]]; then
    dest="$STAGING/abpe_ui/incoming/i18n/$lang"
    mkdir -p "$dest"
    rsync -a --delete "$src/" "$dest/"
    n=$(find "$dest" -name '*.json' | wc -l | tr -d ' ')
    echo "OK: abpe_ui i18n/$lang → $n JSON-Dateien"
  else
    echo "SKIP: abpe_ui i18n/$lang (nicht vorhanden)"
  fi
done

echo ""
echo "=== i18n Sprachordner (CRM) ==="
for lang in de en ar zh hu; do
  src="$BACKEND/apps/abpe_crm/static/abpe_crm/i18n/$lang"
  if [[ -d "$src" ]]; then
    dest="$STAGING/abpe_crm/incoming/i18n/$lang"
    mkdir -p "$dest"
    rsync -a --delete "$src/" "$dest/"
    n=$(find "$dest" -name '*.json' | wc -l | tr -d ' ')
    echo "OK: abpe_crm i18n/$lang → $n JSON-Dateien"
  else
    echo "SKIP: abpe_crm i18n/$lang (nicht vorhanden)"
  fi
done

echo ""
echo "=== Staging → Git-Clone ==="
rsync -a "$STAGING/abpe_ui/incoming/" "$REPO/Repo_abpe/abpe_ui/incoming/"
rsync -a "$STAGING/abpe_crm/incoming/"   "$REPO/Repo_abpe/abpe_crm/incoming/"
rsync -a "$STAGING/email_studio/incoming/" "$REPO/Repo_abpe/email_studio/incoming/" 2>/dev/null || true
rm -rf "$REPO/Repo_abpe/abpe_ui/incoming/modules/opt"

echo ""
echo "=== SYNC fertig ==="
echo "  cd $REPO"
echo "  git add Repo_abpe/"
echo "  git status"
echo "  git commit -m 'Live sync: compose + i18n'"
echo "  git push"
echo ""
echo "Erst NACH push: Agent analysiert."
