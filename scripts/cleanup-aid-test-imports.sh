#!/usr/bin/env bash
# Test-AID-Importe auf ucs5 inventarisieren / löschen.
#
#   cd /mnt/public/udoo-reprap
#   bash scripts/cleanup-aid-test-imports.sh              # Inventar
#   bash scripts/cleanup-aid-test-imports.sh dry           # Preset tests Dry-Run
#   bash scripts/cleanup-aid-test-imports.sh delete        # Preset tests + neu/cv
#   bash scripts/cleanup-aid-test-imports.sh delete-since  # seit 2026-08-01
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
MODE="${1:-inventory}"
SINCE="${SINCE:-2026-08-01}"

cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate

case "$MODE" in
  inventory|"")
    python3 manage.py cleanup_aid_test_imports
    ;;
  dry)
    python3 manage.py cleanup_aid_test_imports --preset tests --dry-run
    echo
    python3 manage.py cleanup_aid_test_imports --since "$SINCE" --dry-run
    ;;
  delete)
    echo "WARN: löscht Preset tests (random10+golden) inkl. neu/cv"
    python3 manage.py cleanup_aid_test_imports --preset tests --yes --neu-cv --uploads
    ;;
  delete-since)
    echo "WARN: löscht alle aid_import seit $SINCE inkl. neu/cv"
    python3 manage.py cleanup_aid_test_imports --since "$SINCE" --yes --neu-cv --uploads
    ;;
  *)
    echo "Usage: $0 [inventory|dry|delete|delete-since]" >&2
    exit 2
    ;;
esac
