#!/usr/bin/env bash
# Live → Repo: Shaduler/Posteingang/Radar Allowlist (kein Blind-Overwrite anderer Apps).
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin && git checkout cursor/posteingang-radar-fix-1532 && git pull
#   bash scripts/PULL-posteingang-radar-live-to-repo.sh
#   # prüft Diff, commit lokal — push nur mit PUSH=1
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
BRANCH="${BRANCH:-cursor/posteingang-radar-fix-1532}"
PUSH="${PUSH:-0}"
TS=$(date +%Y%m%d-%H%M%S)

cd "$REPO"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull origin "$BRANCH" || true

MAP=(
  "apps/namazu/management/commands/index_emails.py|Repo_abpe/namazu/incoming/management/commands/index_emails.py"
  "apps/abpe_shaduler/tasks.py|Repo_abpe/abpe_shaduler/incoming/tasks.py"
  "apps/abpe_shaduler/management/commands/register_scheduler_jobs.py|Repo_abpe/abpe_shaduler/incoming/management/commands/register_scheduler_jobs.py"
  "apps/abpe_shaduler/services/inbox_service.py|Repo_abpe/abpe_shaduler/incoming/services/inbox_service.py"
  "apps/abpe_shaduler/services/radar_fetcher.py|Repo_abpe/abpe_shaduler/incoming/services/radar_fetcher.py"
  "apps/abpe_shaduler/services/radar_grouper.py|Repo_abpe/abpe_shaduler/incoming/services/radar_grouper.py"
  "apps/abpe_shaduler/services/radar_berater_fl.py|Repo_abpe/abpe_shaduler/incoming/services/radar_berater_fl.py"
  "apps/abpe_shaduler/services/radar_berater_service.py|Repo_abpe/abpe_shaduler/incoming/services/radar_berater_service.py"
  "apps/abpe_ui/static/abpe_ui/js/mod/mod-shaduler.js|Repo_abpe/abpe_ui/incoming/mod-shaduler.js"
  "apps/abpe_ui/static/abpe_ui/css/mod/mod-shaduler.css|Repo_abpe/abpe_ui/incoming/mod-shaduler.css"
)

echo "======== PULL Live→Repo $TS ========"
for pair in "${MAP[@]}"; do
  live="$BACKEND/${pair%%|*}"
  dest="$REPO/${pair##*|}"
  if [[ ! -f "$live" ]]; then
    echo "SKIP live fehlt: $live"
    continue
  fi
  mkdir -p "$(dirname "$dest")"
  if [[ -f "$dest" ]] && cmp -s "$live" "$dest"; then
    echo "SAME ${pair##*|}"
    continue
  fi
  cp -a "$live" "$dest"
  # mirror static js if matching
  if [[ "$dest" == *mod-shaduler.js ]]; then
    cp -a "$dest" "$REPO/Repo_abpe/abpe_ui/incoming/static_abpe_ui/js/mod/mod-shaduler.js"
  fi
  if [[ "$dest" == *mod-shaduler.css ]]; then
    cp -a "$dest" "$REPO/Repo_abpe/abpe_ui/incoming/static_abpe_ui/css/mod/mod-shaduler.css"
  fi
  echo "PULL ${pair##*|}"
done

git add Repo_abpe/namazu Repo_abpe/abpe_shaduler Repo_abpe/abpe_ui/incoming/mod-shaduler.js \
  Repo_abpe/abpe_ui/incoming/mod-shaduler.css \
  Repo_abpe/abpe_ui/incoming/static_abpe_ui/js/mod/mod-shaduler.js \
  Repo_abpe/abpe_ui/incoming/static_abpe_ui/css/mod/mod-shaduler.css 2>/dev/null || true

git status -sb
if git diff --cached --quiet; then
  echo "Nichts zu committen."
  exit 0
fi
git commit -m "pull(live): Posteingang/Radar Stand ucs5 $TS"
if [[ "$PUSH" == "1" ]]; then
  git push -u origin "$BRANCH"
  echo "OK pushed"
else
  echo "Lokal committed. Push: PUSH=1 bash scripts/PULL-posteingang-radar-live-to-repo.sh"
fi
