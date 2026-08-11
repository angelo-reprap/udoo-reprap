#!/usr/bin/env bash
# Live → Repo: alle Shaduler-Sprachpakete (alle Sprachen) + module.json
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/shaduler-all-in-one-7f07
#   bash <(git show origin/cursor/shaduler-all-in-one-7f07:scripts/PULL-shaduler-i18n-all.sh)
#   git add Repo_abpe/abpe_ui/incoming/i18n Repo_abpe/abpe_ui/incoming/modules/shaduler \
#           Repo_abpe/abpe_ui/incoming/static_abpe_ui/i18n
#   git commit -m "pull(live): Shaduler i18n all languages"
#   git push
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
DEST_UI="$REPO/Repo_abpe/abpe_ui/incoming"

cd "$REPO"
mkdir -p "$DEST_UI/i18n" "$DEST_UI/static_abpe_ui/i18n" "$DEST_UI/modules/shaduler"

if [[ -f "$LIVE_UI/templates/abpe_ui/modules/shaduler/module.json" ]]; then
  cp -a "$LIVE_UI/templates/abpe_ui/modules/shaduler/module.json" \
    "$DEST_UI/modules/shaduler/module.json"
  echo "+ module.json"
fi

n=0
for lang_dir in "$LIVE_UI/static/abpe_ui/i18n"/*; do
  [[ -d "$lang_dir" ]] || continue
  lang=$(basename "$lang_dir")
  src="$lang_dir/modules/shaduler"
  [[ -d "$src" ]] || continue
  mkdir -p "$DEST_UI/i18n/$lang/modules/shaduler"
  mkdir -p "$DEST_UI/static_abpe_ui/i18n/$lang/modules/shaduler"
  cp -a "$src/." "$DEST_UI/i18n/$lang/modules/shaduler/"
  cp -a "$src/." "$DEST_UI/static_abpe_ui/i18n/$lang/modules/shaduler/"
  echo "+ i18n/$lang/modules/shaduler"
  n=$((n + 1))
done

echo "OK — $n Sprachen nach $DEST_UI/i18n/"
echo "Stichprobe AR:"
python3 - <<'PY' || true
import json
from pathlib import Path
p = Path("/mnt/public/udoo-reprap/Repo_abpe/abpe_ui/incoming/i18n/ar/modules/shaduler/shaduler.json")
if not p.exists():
    print("  (ar noch nicht im Repo — erst fix_structure auf Live)")
else:
    d = json.loads(p.read_text(encoding="utf-8"))
    sh = d.get("sh") or {}
    for k in ("tab_kalender", "task_new", "stat_geplant", "tab_posteingang"):
        print(f"  sh.{k} = {sh.get(k)!r}")
PY
