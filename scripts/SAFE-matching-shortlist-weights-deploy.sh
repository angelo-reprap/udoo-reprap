#!/usr/bin/env bash
# Deploy MatchingEngine v2.1 — DB-Gewichtung (ConsultantSkill.weight) + optional ES-Recall.
#
# ucs5:
#   cd /mnt/public/udoo-reprap
#   git fetch origin && git checkout cursor/matching-shortlist-weights-1532 && git pull
#   bash scripts/SAFE-matching-shortlist-weights-deploy.sh
#   # optional settings.json:
#   #   matching.es_recall.enabled=true
#   #   matching.es_recall.index=abpe_matching_profiles_probe
#   MATCH_PROJECT=<uuid|project_number> bash scripts/PROBE-matching-shortlist-weights.sh
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
LIVE_MW="${LIVE_MW:-/opt/abpe/backend/apps/abpe_matching_workflow}"
TS=$(date +%Y%m%d-%H%M%S)

SRC="$REPO/Repo_abpe/abpe_matching_workflow/incoming/services/matching_engine.py"
DST="$LIVE_MW/services/matching_engine.py"

[[ -f "$SRC" ]] || { echo "FAIL: $SRC"; exit 1; }
[[ -d "$LIVE_MW/services" ]] || { echo "FAIL: $LIVE_MW/services"; exit 1; }

if ! grep -q "weighted_v2" "$SRC"; then
  echo "FAIL: Repo matching_engine.py ohne weighted_v2"
  exit 1
fi
if ! grep -q "würde Blindlinge liefern" "$SRC"; then
  echo "FAIL: Repo matching_engine.py ohne Empty-Skills Guard"
  exit 1
fi

if [[ -f "$DST" ]]; then
  cp -a "$DST" "$DST.bak-shortlist-weights-$TS"
  echo "Backup → $DST.bak-shortlist-weights-$TS"
fi
cp -a "$SRC" "$DST"
echo "OK matching_engine.py → $DST"

# Cache
find "$LIVE_MW" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Soft-Hinweis settings.json (kein Auto-Write)
SETTINGS="${SETTINGS:-/opt/abpe/backend/settings.json}"
if [[ -f "$SETTINGS" ]]; then
  if ! grep -q 'es_recall' "$SETTINGS" 2>/dev/null; then
    echo "HINWEIS: settings.json ohne matching.es_recall — Engine nutzt Defaults"
    echo "  (enabled=true soft, index=abpe_matching_profiles_probe, fail-open)"
  fi
fi

echo "Deploy fertig."
echo "Probe: MATCH_PROJECT=<id> bash scripts/PROBE-matching-shortlist-weights.sh"
echo "Oder Portal: Shortlist → Matching starten (nach Django-Reload / Request)."
