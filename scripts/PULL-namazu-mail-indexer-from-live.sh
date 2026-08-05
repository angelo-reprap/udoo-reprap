#!/usr/bin/env bash
# Live → Repo: Namazu-Mail-Indexer (abpe_emails) nach Repo_abpe/namazu/incoming/
#
# Der Posteingang LIEST nur abpe_emails — befüllt wird der Index von namazu
# (nicht vom Shaduler / nicht von Celery-Beat).
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap && git fetch origin cursor/abpe-shaduler-scaffold-7f07
#   bash <(git show origin/cursor/abpe-shaduler-scaffold-7f07:scripts/PULL-namazu-mail-indexer-from-live.sh)
set -euo pipefail

LIVE_APP="${LIVE_APP:-/opt/abpe/backend/apps/namazu}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
DEST="$REPO/Repo_abpe/namazu/incoming"
BRANCH="${BRANCH:-cursor/abpe-shaduler-scaffold-7f07}"

if [[ ! -d "$LIVE_APP" ]]; then
  echo "FAIL: $LIVE_APP fehlt."
  echo "Suche Alternativen:"
  ls /opt/abpe/backend/apps/ | grep -iE 'namazu|mail|imap|automail' || true
  exit 1
fi

mkdir -p "$DEST"

echo "== Dateien mit abpe_emails =="
mapfile -t HITS < <(grep -rl 'abpe_emails' "$LIVE_APP" --include='*.py' --include='*.json' --include='*.md' 2>/dev/null || true)
if [[ ${#HITS[@]} -eq 0 ]]; then
  echo "(keine Treffer auf abpe_emails — kopiere management/commands + services grob)"
  rsync -a --relative \
    --exclude '__pycache__/' --exclude '*.pyc' \
    "$LIVE_APP/./management" \
    "$LIVE_APP/./services" \
    "$DEST/" 2>/dev/null || true
else
  for f in "${HITS[@]}"; do
    rel="${f#"$LIVE_APP"/}"
    mkdir -p "$DEST/$(dirname "$rel")"
    cp -a "$f" "$DEST/$rel"
    echo "  + $rel"
  done
fi

# email_settings.json ist die Account-Quelle für den Indexer
for cand in \
  "$LIVE_APP/management/commands/email_settings.json" \
  "$LIVE_APP/email_settings.json" \
  /opt/abpe/backend/apps/namazu/management/commands/email_settings.json
do
  if [[ -f "$cand" ]]; then
    mkdir -p "$DEST/management/commands"
    # Passwörter redakten fürs Repo
    python3 - "$cand" "$DEST/management/commands/email_settings.json" <<'PY'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
data = json.load(open(src, encoding='utf-8'))
accs = data.get('accounts') or {}
if isinstance(accs, dict):
    for k, v in list(accs.items()):
        if isinstance(v, dict) and 'password' in v:
            v = dict(v)
            v['password'] = '***REDACTED***'
            accs[k] = v
json.dump(data, open(dst, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print(f"  + management/commands/email_settings.json (passwords redacted) from {src}")
PY
    break
  fi
done

# Typische Command-Namen zusätzlich (falls ohne String-Treffer)
for cmd in index_emails sync_emails imap_to_es email_index mail_index index_mailboxes; do
  f="$LIVE_APP/management/commands/${cmd}.py"
  if [[ -f "$f" ]]; then
    mkdir -p "$DEST/management/commands"
    cp -a "$f" "$DEST/management/commands/"
    echo "  + management/commands/${cmd}.py"
  fi
done

echo
echo "OK → $DEST ($(find "$DEST" -type f ! -path '*/__pycache__/*' | wc -l) Dateien)"
echo
echo "Diagnose auf Live (Indexer finden):"
echo "  grep -rn abpe_emails /opt/abpe/backend/apps/namazu --include='*.py' | head"
echo "  ls /opt/abpe/backend/apps/namazu/management/commands/"
echo "  supervisorctl status | grep -iE 'mail|imap|namazu|celery|sched'"
echo
echo "Danach commit/push:"
echo "  cd $REPO && git checkout $BRANCH && git pull origin $BRANCH"
echo "  git add Repo_abpe/namazu/incoming && git commit -m 'Import: namazu Mail-Indexer (abpe_emails)' && git push"
