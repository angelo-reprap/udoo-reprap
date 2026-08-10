#!/usr/bin/env bash
# Repo → Live: nur namazu index_emails.py (NICHT email_settings.json — Passwörter!).
set -euo pipefail
REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-origin/cursor/posteingang-es-stale-7f07}"
LIVE_CMD="${LIVE_CMD:-/opt/abpe/backend/apps/namazu/management/commands}"

cd "$REPO"
git fetch origin cursor/posteingang-es-stale-7f07 || true

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git archive "$BRANCH" Repo_abpe/namazu/incoming/management/commands/index_emails.py | tar -x -C "$TMP"

SRC="$TMP/Repo_abpe/namazu/incoming/management/commands/index_emails.py"
if [[ ! -f "$SRC" ]]; then
  echo "FAIL: index_emails.py nicht im Branch"
  exit 1
fi

mkdir -p "$LIVE_CMD"
# Backup Live
if [[ -f "$LIVE_CMD/index_emails.py" ]]; then
  cp -a "$LIVE_CMD/index_emails.py" "$LIVE_CMD/index_emails.py.bak.$(date +%Y%m%d_%H%M%S)"
fi
cp -a "$SRC" "$LIVE_CMD/index_emails.py"

echo "OK → $LIVE_CMD/index_emails.py"
echo "email_settings.json wurde NICHT angefasst (Live-Passwörter bleiben)."
echo
echo "Wichtig: leere IMAP-SINCE-Suche prunt NICHT mehr das ES-Fenster."
echo
echo "Shaduler SYNC + Job (since_days=7) setzen:"
echo "  bash <(git show origin/cursor/posteingang-es-stale-7f07:scripts/SYNC-abpe-shaduler-files.sh)"
echo "  supervisorctl restart abpe-django abpe-celery"
echo "  cd /opt/abpe/backend && /opt/abpe/venv311/bin/python manage.py register_scheduler_jobs"
echo
echo "Catch-up (stellt die letzten Tage wieder her):"
echo "  cd /opt/abpe/backend && /opt/abpe/venv311/bin/python manage.py index_emails --since-days 14 --folders INBOX --no-prune"
echo "Dann Probe:"
echo "  /opt/abpe/venv311/bin/python manage.py shaduler_inbox_probe --fetch --limit 5"
