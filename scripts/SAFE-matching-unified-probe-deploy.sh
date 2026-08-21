#!/usr/bin/env bash
# Deploy Probe-Code (matching_weight_probe + management command) nach Live-Shaduler.
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
LIVE_SH="${LIVE_SH:-/opt/abpe/backend/apps/abpe_shaduler}"
TS=$(date +%Y%m%d-%H%M%S)

SRC="$REPO/Repo_abpe/abpe_shaduler/incoming"
[[ -d "$SRC" ]] || { echo "FAIL: $SRC"; exit 1; }
[[ -d "$LIVE_SH" ]] || { echo "FAIL: $LIVE_SH"; exit 1; }

mkdir -p "$LIVE_SH/services" "$LIVE_SH/management/commands"
for f in \
  services/matching_weight_probe.py \
  management/commands/probe_matching_unified_index.py
do
  if [[ -f "$LIVE_SH/$f" ]]; then
    cp -a "$LIVE_SH/$f" "$LIVE_SH/${f}.bak-probe-$TS"
  fi
  cp -a "$SRC/$f" "$LIVE_SH/$f"
  echo "OK $f"
done

# services/__init__ falls nötig
[[ -f "$LIVE_SH/services/__init__.py" ]] || touch "$LIVE_SH/services/__init__.py"

find "$LIVE_SH" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
echo "Deploy fertig. Danach: bash scripts/PROBE-matching-unified-index.sh"
