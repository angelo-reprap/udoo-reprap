#!/usr/bin/env bash
# DE → alle Shaduler-Sprachen neu übersetzen (Deepseek auf Live).
#
# 1) Aktuelles DE + i18n-bin aus Branch nach Live
# 2) Nicht-DE shaduler.json löschen (--wipe) + Locale-Müll aufräumen
# 3) Deepseek-Neuübersetzung aller Portal-Sprachen
# 4) Hinweis: PULL zurück ins Repo
#
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/shaduler-all-in-one-7f07
#   bash <(git show origin/cursor/shaduler-all-in-one-7f07:scripts/RETRANSLATE-shaduler-i18n-from-de.sh)
#
# Optional nur eine Sprache (NICHT $LANG — das ist die System-Locale!):
#   ONLY_LANG=zh bash <(git show …:scripts/RETRANSLATE-shaduler-i18n-from-de.sh)
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-origin/cursor/shaduler-all-in-one-7f07}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
LIVE_UI="${LIVE_UI:-$BACKEND/apps/abpe_ui}"
LIVE_BIN="${LIVE_BIN:-$BACKEND/apps/abpe_shaduler/bin}"
PYBIN="${PYBIN:-python3}"
# Wichtig: nur ONLY_LANG / SHADULER_LANG — niemals $LANG (Locale en_US.UTF-8)!
ONLY_LANG="${ONLY_LANG:-${SHADULER_LANG:-}}"

echo "======== RETRANSLATE shaduler i18n from DE $(date -Iseconds) ========"
echo "Branch: $BRANCH"
echo "Backend: $BACKEND"
echo

# Abwehren: versehentlich Locale statt Sprachcode
if [[ -n "$ONLY_LANG" ]]; then
  if [[ ! "$ONLY_LANG" =~ ^[a-z]{2}(-[a-z]{2})?$ ]]; then
    echo "FEHLER: ONLY_LANG='$ONLY_LANG' ist kein Sprachcode (erwartet z.B. en, zh, ar)."
    echo "Hinweis: \$LANG ist die System-Locale — bitte ONLY_LANG=zh verwenden."
    exit 1
  fi
fi

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

I18N="$LIVE_UI/static/abpe_ui/i18n"
if [[ ! -d "$I18N" ]]; then
  echo "FEHLER: $I18N fehlt"
  exit 1
fi

# Locale-/Müll-Ordner entfernen (z.B. en_US.UTF-8 durch alten LANG-Bug)
echo
echo "── Aufräumen ungültiger Sprachordner ──"
for d in "$I18N"/*; do
  [[ -d "$d" ]] || continue
  name=$(basename "$d")
  if [[ ! "$name" =~ ^[a-z]{2}(-[a-z]{2})?$ ]]; then
    echo "  🗑  $name (kein ISO-Sprachcode)"
    rm -rf "$d"
  fi
done

echo
echo "── Deepseek Neuübersetzung ──"
cd "$BACKEND"
EXTRA=()
if [[ -n "$ONLY_LANG" ]]; then
  EXTRA=(--lang "$ONLY_LANG")
  echo "Nur Sprache: $ONLY_LANG"
else
  echo "Alle Portal-Sprachen (außer de)"
fi

$PYBIN apps/abpe_shaduler/bin/i18n_translator.py --wipe "${EXTRA[@]}"

echo
echo "======== Fertig ========"
echo "Nächste Schritte (Repo aktualisieren):"
echo "  cd $REPO"
echo "  git fetch origin && git reset --hard origin/cursor/shaduler-all-in-one-7f07"
echo "  bash scripts/PULL-shaduler-i18n-all.sh"
echo "  # oder: bash <(git show origin/cursor/shaduler-all-in-one-7f07:scripts/PULL-shaduler-i18n-all.sh)"
echo "  git add Repo_abpe/abpe_ui/incoming/i18n Repo_abpe/abpe_ui/incoming/static_abpe_ui/i18n \\"
echo "          Repo_abpe/abpe_ui/incoming/modules/shaduler"
echo "  git commit -m 'pull(live): Shaduler i18n retranslated from DE'"
echo "  git push origin cursor/shaduler-all-in-one-7f07"
echo
echo "Dann Full-SYNC oder Ctrl+F5 nach collectstatic."
