#!/usr/bin/env bash
# =============================================================================
# HYGIENE-matching-indexes.sh
# -----------------------------------------------------------------------------
# Orchestriert Säubern + robustes Aktualisieren der Matching-relevanten Indizes.
#
# Phasen:
#   0) Inventur ES + Health (read-only)
#   1) Scheduler-Junk löschen (meetme/e2e/test)
#   2) 5 Periodics sicherstellen (radar/inbox/prozess/email/radar_berater)
#   3) AID-ES abpe_consultants_index aus DB nachziehen
#   4) Health erneut
#
# Default: DRY (keine Schreibzugriffe außer wenn EXECUTE=1).
#
# ucs5:
#   cd /mnt/public/udoo-reprap
#   git fetch origin && git checkout cursor/matching-index-hygiene-1532 && git pull
#
#   # erst ansehen:
#   bash scripts/HYGIENE-matching-indexes.sh
#
#   # dann schreiben:
#   EXECUTE=1 bash scripts/HYGIENE-matching-indexes.sh
#
#   # AID-ES erst mit Limit testen:
#   EXECUTE=1 AID_LIMIT=100 bash scripts/HYGIENE-matching-indexes.sh
#
# Optional Experiment-Indizes (nach INVENTORY-es-indexes.sh):
#   EXECUTE=1 INDEXES=abpe_profiles_v2,abpe_profile_versions \
#     bash scripts/CLEANUP-es-candidate-indexes.sh
#
# Namazu-ES (abpe_namazu_profiles) ist seit Juni stale — Full-Reindex ist
# ein eigener Schritt (HTML unter /var/www/namazu/index → ES). Hier nur Report.
# =============================================================================
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXECUTE="${EXECUTE:-0}"
AID_LIMIT="${AID_LIMIT:-0}"
SKIP_SCHEDULER="${SKIP_SCHEDULER:-0}"
SKIP_AID="${SKIP_AID:-0}"
SKIP_INVENTORY="${SKIP_INVENTORY:-0}"

echo "======== Matching Index Hygiene ========"
echo "EXECUTE=$EXECUTE AID_LIMIT=$AID_LIMIT"
echo "REPO=$REPO"
echo ""

cd "$REPO"

if [[ "$SKIP_INVENTORY" != "1" ]]; then
  echo "── Phase 0a: ES Inventur ──"
  bash "$SCRIPT_DIR/INVENTORY-es-indexes.sh" || true
  echo
  echo "── Phase 0b: Health ──"
  bash "$SCRIPT_DIR/CHECK-matching-index-health.sh" || true
  echo
fi

if [[ "$SKIP_SCHEDULER" != "1" ]]; then
  echo "── Phase 1: Scheduler Junk ──"
  if [[ "$EXECUTE" == "1" ]]; then
    # Hart löschen (nicht nur cancel) — Tests sollen weg
    MODE=delete EXECUTE=1 bash "$SCRIPT_DIR/CLEANUP-scheduler-junk-jobs.sh"
  else
    bash "$SCRIPT_DIR/CLEANUP-scheduler-junk-jobs.sh"
  fi
  echo
  echo "── Phase 2: Periodics sicherstellen ──"
  if [[ "$EXECUTE" == "1" ]]; then
    bash "$SCRIPT_DIR/ENSURE-matching-index-scheduler-jobs.sh"
  else
    DRY_RUN=1 bash "$SCRIPT_DIR/ENSURE-matching-index-scheduler-jobs.sh" || \
      bash "$SCRIPT_DIR/ENSURE-matching-index-scheduler-jobs.sh"
  fi
  echo
fi

if [[ "$SKIP_AID" != "1" ]]; then
  echo "── Phase 3: AID-ES Repair ──"
  if [[ "$EXECUTE" == "1" ]]; then
    if [[ "${AID_LIMIT}" != "0" ]]; then
      EXECUTE=1 LIMIT="$AID_LIMIT" bash "$SCRIPT_DIR/REPAIR-aid-consultants-es-index.sh"
    else
      EXECUTE=1 bash "$SCRIPT_DIR/REPAIR-aid-consultants-es-index.sh"
    fi
  else
    bash "$SCRIPT_DIR/REPAIR-aid-consultants-es-index.sh"
  fi
  echo
fi

echo "── Phase 4: Health final ──"
bash "$SCRIPT_DIR/CHECK-matching-index-health.sh" || true

echo
echo "======== Fertig ========"
if [[ "$EXECUTE" != "1" ]]; then
  echo "DRY-RUN. Zum Schreiben:"
  echo "  EXECUTE=1 AID_LIMIT=100 bash scripts/HYGIENE-matching-indexes.sh"
  echo "  EXECUTE=1 bash scripts/HYGIENE-matching-indexes.sh"
else
  echo "Geschrieben. Erwartung:"
  echo "  Scheduler: ~5 Jobs (keine meetme/e2e)"
  echo "  abpe_consultants_index ≈ DB completed+validated+profile_ready (dedup)"
  echo "  Periodics: radar_poll, inbox_poll, prozess_tick, email_index, radar_berater_index"
  echo
  echo "Offen (bewusst nicht auto):"
  echo "  - abpe_namazu_profiles Refresh (HTML aktuell, ES indexed_at alt)"
  echo "  - Experiment-Indizes: INVENTORY-es-indexes.sh → CLEANUP-es-candidate-indexes.sh"
fi
