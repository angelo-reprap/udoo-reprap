#!/usr/bin/env bash
# Deprecated wrapper: gleiche Quelle wie alle Kanban-Stage-Vorlagen.
# Früher nur matching_outreach_wizard — das überschrieb leicht einen alten Stand.
#
# ucs5:
#   cd /mnt/public/udoo-reprap
#   git pull origin cursor/matching-stage-mail-templates-1532
#   bash scripts/SAFE-ensure-matching-stage-templates.sh
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
STAGE="$REPO/scripts/SAFE-ensure-matching-stage-templates.sh"

[[ -f "$STAGE" ]] || { echo "FAIL: $STAGE fehlt"; exit 1; }
echo "WARN: SAFE-ensure-matching-outreach-wizard-template.sh ist ein Wrapper."
echo "      Nutze bevorzugt: bash scripts/SAFE-ensure-matching-stage-templates.sh"
exec bash "$STAGE"
