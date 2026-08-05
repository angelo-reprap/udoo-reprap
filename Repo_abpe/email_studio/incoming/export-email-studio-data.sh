#!/usr/bin/env bash
# Exportiert Email-Studio-DB (Module, Vorlagen, Signaturen, Absender) ins Git-Repo.
#
# Auf ucs5 ausführen:
#   cd /mnt/public/udoo-reprap && git pull
#   bash Repo_abpe/email_studio/incoming/export-email-studio-data.sh
#
# Optional:
#   SNAPSHOT_DATE=2026-07-18 bash …/export-email-studio-data.sh
#   ABPE_BACKEND=/opt/abpe/backend REPO=/mnt/public/udoo-reprap bash …
#
# Danach: git add / commit / push (oder RUN-phase1-iststand.sh --commit)

set -euo pipefail

BE="${ABPE_BACKEND:-/opt/abpe/backend}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
VENV="${ABPE_VENV:-/opt/abpe/venv311}"
DATA_DIR="${REPO}/Repo_abpe/email_studio/data"
DATE_TAG="${SNAPSHOT_DATE:-$(date +%Y-%m-%d)}"
OUT="${DATA_DIR}/email_studio_snapshot_${DATE_TAG}.json"

MODELS=(
  abpe_email_studio.EmailModule
  abpe_email_studio.EmailTemplate
  abpe_email_studio.EmailSignature
  abpe_email_studio.EmailSenderAccount
)

if [[ ! -d "$BE" ]]; then
  echo "Fehler: Backend nicht gefunden: $BE" >&2
  exit 1
fi

if [[ ! -x "${VENV}/bin/python" ]]; then
  echo "Fehler: venv nicht gefunden: ${VENV}/bin/python" >&2
  exit 1
fi

mkdir -p "$DATA_DIR"

# Symlink / latest pointer for agents
LATEST="${DATA_DIR}/email_studio_snapshot_latest.json"

echo "→ dumpdata ${MODELS[*]}"
echo "  Ziel: $OUT"

(
  cd "$BE"
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
  python manage.py dumpdata "${MODELS[@]}" \
    --indent 2 \
    -o "$OUT"
)

# Also write/update "latest" copy (same content) for stable agent paths
cp -a "$OUT" "$LATEST"

BYTES=$(wc -c < "$OUT" | tr -d ' ')
echo ""
echo "OK: Snapshot geschrieben (${BYTES} bytes)"
echo "    $OUT"
echo "    $LATEST"
echo ""
echo "Nächster Schritt:"
echo "  cd $REPO"
echo "  git add Repo_abpe/email_studio/data/"
echo "  git commit -m \"chore(email-studio): DB-Snapshot Module, Vorlagen, Signaturen\""
echo "  git push"
