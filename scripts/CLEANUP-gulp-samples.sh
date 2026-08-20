#!/usr/bin/env bash
# Entfernt temporäre gulp TXT-Samples wieder aus dem Repo (nach Keyword-Härtung).
# Behält die kleinen 29er-Samples unter artifacts/gulp-samples/ optional.
#
#   KEEP_SMALL=1 bash scripts/CLEANUP-gulp-samples.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

removed=0
for d in artifacts/gulp-samples-1000 artifacts/gulp-samples-tmp; do
  if [[ -d "$d" ]]; then
    echo "remove $d"
    rm -rf "$d"
    git rm -r --ignore-unmatch "$d" 2>/dev/null || true
    removed=1
  fi
done

# große Analyse-Ordner unter gulp-samples (nicht die 29 txt)
if [[ "${PURGE_ALL_GULP_SAMPLES:-0}" == "1" ]]; then
  if [[ -d artifacts/gulp-samples ]]; then
    echo "PURGE_ALL: remove artifacts/gulp-samples"
    rm -rf artifacts/gulp-samples
    git rm -r --ignore-unmatch artifacts/gulp-samples 2>/dev/null || true
    removed=1
  fi
elif [[ "${KEEP_SMALL:-1}" == "1" ]]; then
  # nur keyword-* Unterordner weg, txt behalten
  shopt -s nullglob
  for d in artifacts/gulp-samples/keyword-*; do
    echo "remove $d"
    rm -rf "$d"
    removed=1
  done
  shopt -u nullglob
fi

if [[ "$removed" -eq 0 ]]; then
  echo "nichts zu löschen"
  exit 0
fi

echo
echo "Danach committen:"
echo "  git add -A artifacts/gulp-samples* scripts/CLEANUP-gulp-samples.sh"
echo "  git status"
echo "  git commit -m 'chore: remove temp 1000 gulp txt after keyword harden'"
echo "  git push"
