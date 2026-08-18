#!/usr/bin/env bash
# Live: namazu-Indexer deployen, Catch-up (1 Account schnell), Probe.
# Auf ucs5 ausführen:
#   bash <(git -C /mnt/public/udoo-reprap show origin/cursor/abpe-shaduler-scaffold-7f07:scripts/TEST-namazu-index-live.sh)
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-origin/cursor/abpe-shaduler-scaffold-7f07}"
PY="${PY:-/opt/abpe/venv311/bin/python}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
ACCOUNT="${ACCOUNT:-vertrieb}"
SINCE_DAYS="${SINCE_DAYS:-90}"

cd "$REPO"
git fetch origin cursor/abpe-shaduler-scaffold-7f07 || true

echo "=== 1) SYNC index_emails.py ==="
bash <(git show "$BRANCH:scripts/SYNC-namazu-index-emails.sh")

echo
echo "=== 2) SYNC shaduler (webhook email-index) ==="
bash <(git show "$BRANCH:scripts/SYNC-abpe-shaduler-files.sh")
supervisorctl restart abpe-django
sleep 2

echo
echo "=== 3) Unit-ähnlicher Smoke: Import Command ==="
cd "$BACKEND"
$PY - <<'PY'
from apps.namazu.management.commands import index_emails as m
assert hasattr(m, 'sane_date_iso')
assert m.sane_date_iso('4501-01-01T01:00:00+01:00') is None
assert m.sane_date_iso('Wed, 03 Jun 2026 12:00:00 +0200') is not None
src = open(m.__file__).read()
assert 'size_bytes = len(raw)' in src
print('OK smoke: sane_date + size_bytes')
PY

echo
echo "=== 4) Index Catch-up: account=$ACCOUNT since_days=$SINCE_DAYS (INBOX) ==="
$PY manage.py index_emails --account "$ACCOUNT" --since-days "$SINCE_DAYS"

echo
echo "=== 5) Scheduler-Jobs (inkl. email_index) ==="
$PY manage.py register_scheduler_jobs || echo "WARN: register_scheduler_jobs failed (Token?)"

echo
echo "=== 6) Probe ==="
$PY manage.py shaduler_inbox_probe --fetch --limit 5

echo
echo "=== 7) ES newest (sane) ==="
curl -s 'http://localhost:9200/abpe_emails/_search?pretty' \
  -H 'Content-Type: application/json' \
  -d '{"size":1,"sort":[{"date":"desc"}],"query":{"range":{"date":{"gte":"2000-01-01","lte":"now+1d"}}},"_source":["date","account","subject","folder"]}' \
  | head -c 1200
echo
echo "DONE"
