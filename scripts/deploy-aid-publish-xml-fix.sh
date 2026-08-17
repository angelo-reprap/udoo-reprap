#!/usr/bin/env bash
# Deploy nur den Word-XML / HTML→PDF Publish-Fix nach Live — ohne SAFE-Script.
# Auf ucs5 (egal welcher Checkout-Branch):
#   cd /mnt/public/udoo-reprap
#   bash scripts/deploy-aid-publish-xml-fix.sh
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
LIVE_CV="${LIVE_CV:-/opt/abpe/backend/apps/cv_extractor}"
REF="${REF:-origin/cursor/aid-publish-xml-sanitize-1532}"

cd "$REPO"
git fetch origin cursor/aid-publish-xml-sanitize-1532

copy_one() {
  local rel="$1"
  local src_path="Repo_abpe/cv_extractor/incoming/$rel"
  local dst="$LIVE_CV/$rel"
  mkdir -p "$(dirname "$dst")"
  git show "${REF}:${src_path}" > "$dst"
  echo "OK → $dst"
}

copy_one generator/word/word_generator.py
copy_one generator/word/word_builder.py
copy_one services/aid_profile_publish.py

echo
echo "=== Verify ==="
grep -n '_xml_safe' "$LIVE_CV/generator/word/word_generator.py" | head -5
grep -n 'HTML-Fallback' "$LIVE_CV/services/aid_profile_publish.py" | head -3
echo
echo "Fertig. Danach Barnekow/Barth re-import oder Batch mit SKIP_DIRS."
