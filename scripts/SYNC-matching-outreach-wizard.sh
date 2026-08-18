#!/usr/bin/env bash
# Deploy Outreach-Wizard (Matching) auf ucs5 — Convert-Batch unberührt.
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/matching-outreach-wizard-1532
#   bash scripts/SYNC-matching-outreach-wizard.sh
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/matching-outreach-wizard-1532}"
LIVE_MW="${LIVE_MW:-/opt/abpe/backend/apps/abpe_matching_workflow}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
STATICFILES="${STATICFILES:-/opt/abpe/backend/staticfiles}"
TS=$(date +%Y%m%d-%H%M%S)
SKIP_CHECK="${SKIP_CHECK:-0}"
FORCE="${FORCE:-0}"

cd "$REPO"
git fetch origin "$BRANCH"

# ── Guard: Live voraus? Dann kein Blind-Overwrite ───────────────────────────
if [[ "$SKIP_CHECK" != "1" ]]; then
  echo "=== Pre-Check Live ↔ Repo ==="
  LIVE_JS="${LIVE_UI}/static/abpe_ui/js/mod/mod-matching.js"
  if [[ -f "$LIVE_JS" ]] && grep -q "openOutreachWizard" "$LIVE_JS" 2>/dev/null; then
    live_extra=$(grep -c "outreachUnifiedSearch" "$LIVE_JS" 2>/dev/null || echo 0)
    repo_extra=$(git show "origin/$BRANCH:Repo_abpe/abpe_ui/incoming/mod-matching.js" 2>/dev/null | grep -c "outreachUnifiedSearch" || echo 0)
    live_extra=${live_extra//$'\n'/}; repo_extra=${repo_extra//$'\n'/}
    if [[ "$live_extra" -gt "$repo_extra" && "$FORCE" != "1" ]]; then
      echo "ABBRUCH: Live hat outreachUnifiedSearch ($live_extra) > Repo ($repo_extra)."
      echo "Live→Repo pullen, sonst Feature-Verlust. Oder FORCE=1."
      exit 2
    fi
  fi
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git archive "origin/$BRANCH" \
  Repo_abpe/abpe_matching_workflow/incoming \
  Repo_abpe/abpe_crm/incoming/views.py \
  Repo_abpe/abpe_ui/incoming/mod-matching.js \
  Repo_abpe/abpe_ui/incoming/static_abpe_ui/js/mod/mod-matching.js \
  | tar -x -C "$TMP"

echo "=== Outreach Wizard Sync ($BRANCH) ==="

mkdir -p "$LIVE_MW/services"
for rel in views.py urls.py services/outreach_wizard.py; do
  src="$TMP/Repo_abpe/abpe_matching_workflow/incoming/$rel"
  dst="$LIVE_MW/$rel"
  [[ -f "$src" ]] || { echo "FEHLER: fehlt $rel im Branch"; exit 1; }
  mkdir -p "$(dirname "$dst")"
  [[ -f "$dst" ]] && cp -a "$dst" "${dst}.bak-outreach-$TS"
  cp -a "$src" "$dst"
  echo "OK — $rel → $dst"
done

# CRM api_email_send (CC/BCC)
LIVE_CRM="${LIVE_CRM:-/opt/abpe/backend/apps/abpe_crm}"
CRM_SRC="$TMP/Repo_abpe/abpe_crm/incoming/views.py"
CRM_DST="$LIVE_CRM/views.py"
if [[ -f "$CRM_SRC" && -f "$CRM_DST" ]]; then
  if grep -q "cc_extra" "$CRM_SRC"; then
    cp -a "$CRM_DST" "${CRM_DST}.bak-outreach-$TS"
    cp -a "$CRM_SRC" "$CRM_DST"
    echo "OK — abpe_crm/views.py (cc/bcc) → $CRM_DST"
  fi
fi

if ! grep -q "api_outreach_deep_reason" "$LIVE_MW/views.py"; then
  echo "FEHLER: views.py ohne Outreach-APIs"
  exit 1
fi
if ! grep -q "outreach/" "$LIVE_MW/urls.py"; then
  echo "FEHLER: urls.py ohne outreach routes"
  exit 1
fi

# UI: incoming/mod-matching.js ist Deploy-Quelle (wie andere SYNC-Skripte)
JS_SRC="$TMP/Repo_abpe/abpe_ui/incoming/mod-matching.js"
if ! grep -q "openOutreachWizard" "$JS_SRC"; then
  echo "FEHLER: mod-matching.js ohne openOutreachWizard"
  exit 1
fi
if ! grep -q "outreachApplyEmail" "$JS_SRC"; then
  echo "FEHLER: mod-matching.js ohne outreachApplyEmail (E-Mail-Übernehmen)"
  exit 1
fi
if ! grep -q "outreachUnifiedSearch" "$JS_SRC"; then
  echo "FEHLER: mod-matching.js ohne outreachUnifiedSearch"
  exit 1
fi
if ! grep -q "outreachApplyMulti" "$JS_SRC"; then
  echo "FEHLER: mod-matching.js ohne outreachApplyMulti (CC/BCC)"
  exit 1
fi
mkdir -p "$LIVE_UI/static/abpe_ui/js/mod"
[[ -f "$LIVE_UI/static/abpe_ui/js/mod/mod-matching.js" ]] \
  && cp -a "$LIVE_UI/static/abpe_ui/js/mod/mod-matching.js" \
       "$LIVE_UI/static/abpe_ui/js/mod/mod-matching.js.bak-outreach-$TS"
cp -a "$JS_SRC" "$LIVE_UI/static/abpe_ui/js/mod/mod-matching.js"
echo "OK — mod-matching.js → $LIVE_UI/static/abpe_ui/js/mod/"

if [[ -d "$STATICFILES" ]]; then
  mkdir -p "$STATICFILES/abpe_ui/js/mod"
  cp -a "$LIVE_UI/static/abpe_ui/js/mod/mod-matching.js" \
    "$STATICFILES/abpe_ui/js/mod/mod-matching.js"
  echo "OK — staticfiles mirror"
fi

find "$LIVE_MW" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "$LIVE_CRM" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Django reload (gunicorn/uvicorn — soft)
if command -v systemctl >/dev/null 2>&1; then
  if systemctl is-active --quiet abpe-backend 2>/dev/null; then
    systemctl reload abpe-backend 2>/dev/null \
      || systemctl restart abpe-backend 2>/dev/null \
      || echo "WARN: systemctl reload/restart abpe-backend manuell prüfen"
  elif systemctl is-active --quiet gunicorn 2>/dev/null; then
    systemctl reload gunicorn 2>/dev/null || true
  else
    echo "Hinweis: App-Server ggf. manuell neu laden (CRM views + matching geändert)"
  fi
fi

echo
echo "Fertig. Browser: Matching → Shortlist → Ctrl+F5 → „Alle anschreiben“"
echo "CC/BCC: Suche + manuell (a@x.de; b@y.de) + Übernehmen; BCC-Default send@abcona.de"
