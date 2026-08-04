#!/usr/bin/env bash
# Repo → Live: nur namazu index_emails.py (NICHT email_settings.json — Passwörter!).
set -euo pipefail
REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-origin/cursor/abpe-shaduler-scaffold-7f07}"
LIVE_CMD="${LIVE_CMD:-/opt/abpe/backend/apps/namazu/management/commands}"

cd "$REPO"
git fetch origin cursor/abpe-shaduler-scaffold-7f07 || true

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
echo "Gelöschte aus ES entfernen (einmal, z.B. angelo INBOX):"
echo "  cd /opt/abpe/backend && /opt/abpe/venv311/bin/python manage.py index_emails --account angelo --folders INBOX --prune-only --prune-orphans"
echo
echo "Catch-up (INBOX, letzte 14 Tage):"
echo "  cd /opt/abpe/backend && /opt/abpe/venv311/bin/python manage.py index_emails --since-days 14"
echo "Dann Probe:"
echo "  /opt/abpe/venv311/bin/python manage.py shaduler_inbox_probe --fetch --limit 5"
