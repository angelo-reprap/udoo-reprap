#!/usr/bin/env bash
# EIN Befehl: Backup → Apply Live-DB → Phase-1 Sync ins Git
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap && git pull
#   bash Repo_abpe/email_studio/incoming/RUN-apply-consolidation.sh
#
# Flags:
#   --dry-run   nur zeigen, keine DB-/Git-Änderung
#   --no-push   Apply + Commit, kein git push

set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BE="${ABPE_BACKEND:-/opt/abpe/backend}"
VENV="${ABPE_VENV:-/opt/abpe/venv311}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DRY=0
PUSH=1
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --no-push) PUSH=0 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
  esac
done

cd "$REPO"
git pull --ff-only || true

echo "=== 0/3 Prüfe Skript ==="
[[ -f "${SCRIPT_DIR}/apply_layout_consolidation.py" ]] || {
  echo "Fehler: apply_layout_consolidation.py fehlt — git pull / richtiger Branch?" >&2
  exit 1
}

if [[ "$DRY" -eq 1 ]]; then
  echo "=== DRY-RUN Apply (keine DB) ==="
  python3 "${SCRIPT_DIR}/apply_layout_consolidation.py" --dry-run
  echo ""
  echo "Dry-run fertig. Ohne --dry-run würde Backup + --apply-db + Phase-1 folgen."
  exit 0
fi

echo "=== 1/3 Backup dumpdata ==="
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="/tmp/email_studio_backup_before_consolidation_${STAMP}.json"
(
  cd "$BE"
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
  python manage.py dumpdata \
    abpe_email_studio.EmailModule \
    abpe_email_studio.EmailTemplate \
    abpe_email_studio.EmailSignature \
    abpe_email_studio.EmailSenderAccount \
    --indent 2 \
    -o "$BACKUP"
)
echo "OK Backup: $BACKUP"

echo ""
echo "=== 2/3 Apply Live-DB ==="
python3 "${SCRIPT_DIR}/apply_layout_consolidation.py" --apply-db

echo ""
echo "=== 3/3 Phase-1 Sync → Git ==="
PHASE_FLAGS=(--commit)
[[ "$PUSH" -eq 1 ]] && PHASE_FLAGS+=(--push)
bash "${SCRIPT_DIR}/RUN-phase1-iststand.sh" "${PHASE_FLAGS[@]}"

echo ""
echo "=== Verify (kurz) ==="
python3 - <<'PY'
import json
from pathlib import Path
p = Path("Repo_abpe/email_studio/data/email_studio_snapshot_latest.json")
rows = json.loads(p.read_text(encoding="utf-8"))
ust = any(
    r["model"].endswith("emailmodule")
    and r["fields"]["identifier"].startswith("footer_")
    and "DE813519516" in (r["fields"].get("html_body") or "")
    for r in rows
)
empty = sum(
    1 for r in rows
    if r["model"].endswith("emailtemplate") and not (r["fields"].get("text_body") or "").strip()
)
modes = {
    r["fields"]["identifier"]: r["fields"].get("signature_mode")
    for r in rows
    if r["model"].endswith("emailtemplate")
    and r["fields"]["identifier"].startswith(("pipeline", "upload"))
}
ok = ust and empty == 0 and all(m == "NONE" for m in modes.values())
print(f"footer_USt={ust} empty_txt={empty} system_modes={modes}")
print("VERIFY_OK" if ok else "VERIFY_FAIL — bitte Output prüfen")
raise SystemExit(0 if ok else 1)
PY

echo ""
echo "Fertig. Backup liegt unter: $BACKUP"
