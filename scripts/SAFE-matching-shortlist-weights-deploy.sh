#!/usr/bin/env bash
# Deploy MatchingEngine v2.1 + Shortlist Quelle (DB/ES) UI.
#
# ucs5:
#   cd /mnt/public/udoo-reprap
#   git fetch origin && git checkout cursor/matching-shortlist-weights-1532 && git pull
#   bash scripts/SAFE-matching-shortlist-weights-deploy.sh
#   MATCH_PROJECT=ANF-2026-0010 bash scripts/PROBE-matching-shortlist-weights.sh
#   # Portal: Shortlist → Erneut matchen → Badges DB/ES + Dropdown
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
LIVE_MW="${LIVE_MW:-/opt/abpe/backend/apps/abpe_matching_workflow}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
STATICFILES="${STATICFILES:-/opt/abpe/backend/staticfiles}"
TS=$(date +%Y%m%d-%H%M%S)

SRC_MW="$REPO/Repo_abpe/abpe_matching_workflow/incoming"
SRC_UI="$REPO/Repo_abpe/abpe_ui/incoming/mod-matching.js"

[[ -d "$SRC_MW" ]] || { echo "FAIL: $SRC_MW"; exit 1; }
[[ -f "$SRC_UI" ]] || { echo "FAIL: $SRC_UI"; exit 1; }
[[ -d "$LIVE_MW/services" ]] || { echo "FAIL: $LIVE_MW/services"; exit 1; }

ENGINE="$SRC_MW/services/matching_engine.py"
if ! grep -q "weighted_v4" "$ENGINE"; then
  echo "FAIL: Repo matching_engine.py ohne weighted_v4"
  exit 1
fi
if ! grep -q "match_source" "$ENGINE"; then
  echo "FAIL: Repo matching_engine.py ohne match_source"
  exit 1
fi
if ! grep -q "würde Blindlinge liefern" "$ENGINE"; then
  echo "FAIL: Repo matching_engine.py ohne Empty-Skills Guard"
  exit 1
fi
if ! grep -q "filterShortlistSource" "$SRC_UI"; then
  echo "FAIL: Repo mod-matching.js ohne filterShortlistSource"
  exit 1
fi

deploy_one() {
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [[ -f "$dst" ]]; then
    cp -a "$dst" "${dst}.bak-shortlist-weights-$TS"
  fi
  cp -a "$src" "$dst"
  echo "OK $(basename "$src") → $dst"
}

deploy_one "$ENGINE" "$LIVE_MW/services/matching_engine.py"
deploy_one "$SRC_MW/views.py" "$LIVE_MW/views.py"
deploy_one "$SRC_MW/tasks.py" "$LIVE_MW/tasks.py"
deploy_one "$SRC_MW/services/matching_service.py" "$LIVE_MW/services/matching_service.py"

# UI
mkdir -p "$LIVE_UI/static/abpe_ui/js/mod"
deploy_one "$SRC_UI" "$LIVE_UI/static/abpe_ui/js/mod/mod-matching.js"
if [[ -d "$STATICFILES/abpe_ui/js/mod" ]]; then
  deploy_one "$SRC_UI" "$STATICFILES/abpe_ui/js/mod/mod-matching.js"
fi

find "$LIVE_MW" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

SETTINGS="${SETTINGS:-/opt/abpe/backend/settings.json}"
if [[ -f "$SETTINGS" ]] && ! grep -q 'es_recall' "$SETTINGS" 2>/dev/null; then
  echo "HINWEIS: settings.json ohne matching.es_recall — Engine nutzt Defaults"
fi

echo "Deploy fertig."
echo "  1) Django/Celery neu laden falls nötig: supervisorctl restart abpe-django abpe-celery"
echo "  2) Browser Ctrl+F5"
echo "  3) Shortlist → Erneut matchen (damit match_source geschrieben wird)"
echo "Probe: MATCH_PROJECT=<id> bash scripts/PROBE-matching-shortlist-weights.sh"
