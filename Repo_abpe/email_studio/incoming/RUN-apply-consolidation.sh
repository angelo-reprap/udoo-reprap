#!/usr/bin/env bash
# EIN Befehl: Backup → Apply Live-DB → KI-Code deployen → Phase-1 Sync → Verify
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap && git pull
#   bash Repo_abpe/email_studio/incoming/RUN-apply-consolidation.sh
#
# Flags:
#   --dry-run   nur zeigen, keine DB-/Git-Änderung
#   --no-push   Apply + Commit, kein git push
#   --db-only   nur DB (kein KI-Deploy)
#   --code-only nur KI-Dateien nach Live kopieren + Sync (DB schon OK)

set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BE="${ABPE_BACKEND:-/opt/abpe/backend}"
VENV="${ABPE_VENV:-/opt/abpe/venv311}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KI_REPO="${REPO}/Repo_abpe/abpe_ki_wiz/incoming"
ES_REPO="${REPO}/Repo_abpe/email_studio/incoming"

DRY=0
PUSH=1
DB=1
CODE=1
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --no-push) PUSH=0 ;;
    --db-only) CODE=0 ;;
    --code-only) DB=0 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
  esac
done

cd "$REPO"
git pull --ff-only || true

echo "=== 0 Prüfe Skript ==="
[[ -f "${SCRIPT_DIR}/apply_layout_consolidation.py" ]] || {
  echo "Fehler: apply_layout_consolidation.py fehlt — git pull / richtiger Branch?" >&2
  exit 1
}

if [[ "$DRY" -eq 1 ]]; then
  echo "=== DRY-RUN Apply (keine DB) ==="
  python3 "${SCRIPT_DIR}/apply_layout_consolidation.py" --dry-run
  echo ""
  echo "Würde danach KI-Dateien nach Live kopieren:"
  echo "  $KI_REPO/providers/email_template.py"
  echo "  $KI_REPO/questions/email_template.json"
  echo "  $ES_REPO/es-core.js → static/.../es-core.js"
  exit 0
fi

BACKUP=""
if [[ "$DB" -eq 1 ]]; then
  echo "=== 1/4 Backup dumpdata ==="
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
  echo "=== 2/4 Apply Live-DB ==="
  python3 "${SCRIPT_DIR}/apply_layout_consolidation.py" --apply-db
else
  echo "=== 1–2/4 DB übersprungen (--code-only) ==="
fi

if [[ "$CODE" -eq 1 ]]; then
  echo ""
  echo "=== 3/4 KI-/Code-Dateien nach Live deployen ==="
  BR="${BE}/apps/abpe_ui/../.."  # unused; keep simple
  copy_one() {
    local src="$1" dest="$2" note="$3"
    if [[ ! -f "$src" ]]; then
      echo "WARN: Quelle fehlt — $src"
      return 0
    fi
    mkdir -p "$(dirname "$dest")"
    if [[ -f "${BE}/Archiv/backup_restore.py" || -f "${BE}/apps/abpe_ui/backup_restore.py" ]]; then
      local brp="${BE}/Archiv/backup_restore.py"
      [[ -f "$brp" ]] || brp="${BE}/apps/abpe_ui/backup_restore.py"
      (
        cd "$BE"
        # shellcheck disable=SC1091
        source "${VENV}/bin/activate"
        # Relativpfad unter backend für -save
        rel="${dest#${BE}/}"
        python3 "$brp" -save "$rel" -m "vor: layout consolidation ${note}" 2>/dev/null || true
      )
    fi
    cp -a "$src" "$dest"
    echo "OK: $src → $dest"
  }

  copy_one \
    "${KI_REPO}/providers/email_template.py" \
    "${BE}/apps/abpe_ki_wiz/providers/email_template.py" \
    "email_template provider"

  copy_one \
    "${KI_REPO}/questions/email_template.json" \
    "${BE}/apps/abpe_ki_wiz/questions/email_template.json" \
    "email_template questions"

  # questions ggf. unter static/questions — beide Pfade absichern
  if [[ -d "${BE}/apps/abpe_ki_wiz/static" ]]; then
    :
  fi
  # Staging-Kopie + Live-Static JS
  copy_one \
    "${ES_REPO}/es-core.js" \
    "${BE}/apps/abpe_email_studio/static/email_studio/js/es-core.js" \
    "es-core cta fix"
  # auch flat staging name if used
  cp -a "${ES_REPO}/es-core.js" "${ES_REPO}/static/email_studio/js/es-core.js" 2>/dev/null || true
else
  echo "=== 3/4 Code-Deploy übersprungen (--db-only) ==="
fi

echo ""
echo "=== 4/4 Phase-1 Sync → Git ==="
PHASE_FLAGS=(--commit)
[[ "$PUSH" -eq 1 ]] && PHASE_FLAGS+=(--push)
bash "${SCRIPT_DIR}/RUN-phase1-iststand.sh" "${PHASE_FLAGS[@]}"

echo ""
echo "=== Verify DB-Snapshot ==="
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
echo "=== Verify KI-Dateien im Repo (nach Sync) ==="
python3 - <<'PY'
from pathlib import Path
et = Path("Repo_abpe/abpe_ki_wiz/incoming/providers/email_template.py").read_text(encoding="utf-8")
qj = Path("Repo_abpe/abpe_ki_wiz/incoming/questions/email_template.json").read_text(encoding="utf-8")
has_xor = "closing_xor" in et
has_cta = "cta_blau" in qj
no_old = "button_blau" not in qj
has_l2 = '"L2"' in qj
ok = has_xor and has_cta and no_old and has_l2
print("closing_xor=%s cta=%s L2=%s" % (has_xor, has_cta, has_l2))
print("VERIFY_KI_OK" if ok else "VERIFY_KI_FAIL — Code-Deploy hat Live nicht erreicht")
raise SystemExit(0 if ok else 1)
PY

echo ""
echo "Fertig."
[[ -n "$BACKUP" ]] && echo "DB-Backup: $BACKUP"
