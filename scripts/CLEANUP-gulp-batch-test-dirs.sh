#!/usr/bin/env bash
# Legacy-Wrapper — bitte das sichere Script nutzen:
#   RESULT_TSV=/tmp/gulp-batch-20260820-175411/result.tsv \
#     bash scripts/SAFE-CLEANUP-gulp-batch-10.sh
#
# Dieses Script leitet weiter (gleiche Env-Vars).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec bash "$ROOT/scripts/SAFE-CLEANUP-gulp-batch-10.sh" "$@"
