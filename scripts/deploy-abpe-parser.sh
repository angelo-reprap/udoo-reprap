#!/usr/bin/env bash
# Deploy experimentelle App apps/abpe_parser auf ucs5 (DeepSeek, kein Ollama).
#
#   cd /mnt/public/udoo-reprap
#   git pull origin cursor/abpe-parser-7f07
#   bash scripts/deploy-abpe-parser.sh
#
# Danach einmalig in Django settings INSTALLED_APPS:
#   'apps.abpe_parser.apps.AbpeParserConfig',
# und Backend neu laden (gunicorn/uwsgi/celery nach Bedarf).
#
# Test:
#   cd /opt/abpe/backend && source venv311/bin/activate
#   python manage.py abpe_parse_resume /pfad/zu/AID.pdf --out /tmp/abpe_parser.json
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/abpe-parser-7f07}"
SRC="$REPO/Repo_abpe/abpe_parser/incoming"
LIVE="${LIVE:-/opt/abpe/backend/apps/abpe_parser}"

cd "$REPO"
git fetch origin "$BRANCH"
# Shared-Mount: immer exakt Remote-Branch (kein divergentes pull.rebase-Drama)
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git checkout "$BRANCH"
else
  git checkout -b "$BRANCH" "origin/$BRANCH"
fi
git reset --hard "origin/$BRANCH"

if [[ ! -d "$SRC" ]]; then
  echo "FAIL: Quelle fehlt: $SRC"
  exit 1
fi

mkdir -p "$LIVE"
rsync -a --delete \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  "$SRC/" "$LIVE/"

echo "OK: $SRC → $LIVE"
echo
echo "Noch nötig (einmalig):"
echo "  1) INSTALLED_APPS += 'apps.abpe_parser.apps.AbpeParserConfig'"
echo "  2) python manage.py abpe_parse_resume <pdf> --out /tmp/out.json"
