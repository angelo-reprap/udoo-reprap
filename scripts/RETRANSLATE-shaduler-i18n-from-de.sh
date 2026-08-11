#!/usr/bin/env bash
# DE → alle Shaduler-Sprachen neu übersetzen (Deepseek auf Live).
#
# 1) Aktuelles DE + i18n-bin aus Branch nach Live
# 2) Nicht-DE shaduler.json löschen (--wipe)
# 3) Deepseek-Neuübersetzung
# 4) Hinweis: PULL zurück ins Repo
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/shaduler-all-in-one-7f07
#   bash <(git show origin/cursor/shaduler-all-in-one-7f07:scripts/RETRANSLATE-shaduler-i18n-from-de.sh)
#
# Optional nur eine Sprache:
#   LANG=zh bash <(git show …:scripts/RETRANSLATE-shaduler-i18n-from-de.sh)
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-origin/cursor/shaduler-all-in-one-7f07}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
LIVE_UI="${LIVE_UI:-$BACKEND/apps/abpe_ui}"
LIVE_BIN="${LIVE_BIN:-$BACKEND/apps/abpe_shaduler/bin}"
PYBIN="${PYBIN:-python3}"
ONLY_LANG="${LANG:-}"

echo "======== RETRANSLATE shaduler i18n from DE $(date -Iseconds) ========"
echo "Branch: $BRANCH"
echo "Backend: $BACKEND"
echo

cd "$REPO"
git fetch origin cursor/shaduler-all-in-one-7f07 || true

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git archive "$BRANCH" \
  Repo_abpe/abpe_shaduler/incoming/bin \
  Repo_abpe/abpe_ui/incoming/i18n/de/modules/shaduler \
  | tar -x -C "$TMP"

# bin deploy
mkdir -p "$LIVE_BIN"
rsync -a --delete \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "$TMP/Repo_abpe/abpe_shaduler/incoming/bin/" \
  "$LIVE_BIN/"
echo "OK — bin → $LIVE_BIN"

# DE-Referenz nach Live (Quelle der Wahrheit)
mkdir -p "$LIVE_UI/static/abpe_ui/i18n/de/modules/shaduler"
cp -a "$TMP/Repo_abpe/abpe_ui/incoming/i18n/de/modules/shaduler/." \
  "$LIVE_UI/static/abpe_ui/i18n/de/modules/shaduler/"
echo "OK — DE-Referenz → $LIVE_UI/static/abpe_ui/i18n/de/modules/shaduler/"

# Portal-Sprachordner müssen existieren (Translator entdeckt sie)
I18N="$LIVE_UI/static/abpe_ui/i18n"
if [[ ! -d "$I18N" ]]; then
  echo "FEHLER: $I18N fehlt"
  exit 1
fi

echo
echo "── Deepseek Neuübersetzung ──"
cd "$BACKEND"
EXTRA=()
if [[ -n "$ONLY_LANG" ]]; then
  EXTRA=(--lang "$ONLY_LANG")
  echo "Nur Sprache: $ONLY_LANG"
fi

$PYBIN apps/abpe_shaduler/bin/i18n_translator.py --wipe "${EXTRA[@]}"

echo
echo "======== Fertig ========"
echo "Nächste Schritte (Repo aktualisieren):"
echo "  cd $REPO"
echo "  bash <(git show $BRANCH:scripts/PULL-shaduler-i18n-all.sh)"
echo "  git add Repo_abpe/abpe_ui/incoming/i18n Repo_abpe/abpe_ui/incoming/static_abpe_ui/i18n \\"
echo "          Repo_abpe/abpe_ui/incoming/modules/shaduler"
echo "  git commit -m 'pull(live): Shaduler i18n retranslated from DE'"
echo "  git push"
echo
echo "Dann Full-SYNC oder Ctrl+F5 nach collectstatic."
