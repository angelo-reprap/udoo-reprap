#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# SAFE Fix: Wolfsegger — falscher Ordner bbb/bernd_www → www/wolfsegger_bernd
# ═══════════════════════════════════════════════════════════════════════════
#
# CRM hat Vorname=Bernd, Nachname=Wolfsegger (contact_id=12026).
# Batch hatte TSV-Shift → AID als „Www Bernd“ unter bbb/bernd_www.
#
# Ablauf (ucs5) — IMMER Dry-Run zuerst:
#
#   bash scripts/FIX-gulp-wolfsegger.sh
#
#   I_UNDERSTAND=yes EXECUTE=1 DRY_RUN=0 bash scripts/FIX-gulp-wolfsegger.sh
#
# Tut nur:
#   1) FS: bbb/bernd_www/neu/ + Convert-PDF entfernen (Stammordner bleibt)
#   2) DB: Consultants mit consultant_dir=bernd_www löschen
#   3) Optional: einen Convert+Import nach www/wolfsegger_bernd
#
set -euo pipefail

AID_ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
EXECUTE="${EXECUTE:-0}"
DRY_RUN="${DRY_RUN:-1}"
I_UNDERSTAND="${I_UNDERSTAND:-}"
REIMPORT="${REIMPORT:-1}"
CONTACT_ID="${CONTACT_ID:-12026}"
WRONG_LETTER=bbb
WRONG_DIR=bernd_www
RIGHT_LETTER=www
RIGHT_DIR=wolfsegger_bernd
LAST=Wolfsegger
FIRST=Bernd

die() { echo "FAIL: $*" >&2; exit 1; }

MODE=DRY-RUN
[[ "$EXECUTE" == "1" && "$DRY_RUN" != "1" ]] && MODE=DELETE

echo "════════════════════════════════════════"
echo " FIX Wolfsegger ($MODE)"
echo "════════════════════════════════════════"
echo "Falsch:  $AID_ROOT/$WRONG_LETTER/$WRONG_DIR"
echo "Richtig: $AID_ROOT/$RIGHT_LETTER/$RIGHT_DIR"
echo "CRM:     $LAST, $FIRST (contact_id=$CONTACT_ID)"
echo "REIMPORT=$REIMPORT"
echo

wrong="$AID_ROOT/$WRONG_LETTER/$WRONG_DIR"
right="$AID_ROOT/$RIGHT_LETTER/$RIGHT_DIR"

echo "── Plan FS ──"
if [[ -d "$wrong" ]]; then
  echo "  rm -rf $wrong/neu/  ($(find "$wrong/neu" -type f 2>/dev/null | wc -l | tr -d ' ') Dateien)"
  find "$wrong" -maxdepth 1 -type f -iname 'AID-*_1.0.0.0.pdf' -printf '  rm %f\n' 2>/dev/null || true
  echo "  behalte $wrong/ (Stamm)"
else
  echo "  (falscher Ordner fehlt schon)"
fi
echo "  Zielordner: $right/ (wird bei REIMPORT angelegt/genutzt)"
echo
echo "── Plan DB ──"
echo "  cleanup_aid_test_imports --dir $WRONG_DIR --any-source"
echo

if [[ "$MODE" != "DELETE" ]]; then
  echo "Dry-run — nichts geändert."
  echo "Zum Ausführen:"
  echo "  I_UNDERSTAND=yes EXECUTE=1 DRY_RUN=0 REIMPORT=$REIMPORT bash $0"
  exit 0
fi

[[ "$I_UNDERSTAND" == "yes" ]] || die "braucht I_UNDERSTAND=yes"

# FS wrong
if [[ -d "$wrong/neu" ]]; then
  echo ">>> rm -rf $wrong/neu"
  rm -rf "$wrong/neu"
fi
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  echo ">>> rm $f"
  rm -f "$f"
done < <(find "$wrong" -maxdepth 1 -type f -iname 'AID-*_1.0.0.0.pdf' 2>/dev/null)

# DB
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
echo ">>> DB delete dir=$WRONG_DIR"
python3 manage.py cleanup_aid_test_imports --dir "$WRONG_DIR" --any-source --yes --limit 16

if [[ "$REIMPORT" != "1" ]]; then
  echo "Fertig (ohne Reimport). Manuell:"
  echo "  LIMIT=1 … mit last=$LAST first=$FIRST dir=$RIGHT_DIR"
  exit 0
fi

# NEED-Zeile aus Inventur oder synthetisch
NEED_SRC="$(ls -td /tmp/gulp-vs-neu-*/need_neu_cv_with_fs_dir.tsv 2>/dev/null | head -1 || true)"
ONE="/tmp/gulp-wolfsegger-one-$$.tsv"
{
  echo -e "cat\tcontact_id\tgulp_id\tlast\tfirst\tfs_letter\tfs_dir\thas_neu_pdf\tprofil_len"
  if [[ -n "$NEED_SRC" && -f "$NEED_SRC" ]]; then
    # Zeile contact_id matchen, Pfad auf CRM-Slug setzen
    awk -F'\t' -v cid="$CONTACT_ID" -v L="$RIGHT_LETTER" -v D="$RIGHT_DIR" -v last="$LAST" -v first="$FIRST" '
      NR==1 {next}
      $2==cid {
        $4=last; $5=first; $6=L; $7=D; $8=0;
        OFS="\t"; $1="fs_dir_no_neu"; print; found=1
      }
      END { if (!found) exit 2 }
    ' "$NEED_SRC" && true
    if [[ $? -eq 2 ]]; then
      # Fallback synthetisch — profil_len aus CRM nicht bekannt
      printf 'fs_dir_no_neu\t%s\t\t%s\t%s\t%s\t%s\t0\t8000\n' \
        "$CONTACT_ID" "$LAST" "$FIRST" "$RIGHT_LETTER" "$RIGHT_DIR"
    fi
  else
    printf 'fs_dir_no_neu\t%s\t\t%s\t%s\t%s\t%s\t0\t8000\n' \
      "$CONTACT_ID" "$LAST" "$FIRST" "$RIGHT_LETTER" "$RIGHT_DIR"
  fi
} >"$ONE"

# Wenn awk exit 2, Datei hat nur Header — Fallback nachschieben
if [[ "$(wc -l <"$ONE" | tr -d ' ')" -lt 2 ]]; then
  printf 'fs_dir_no_neu\t%s\t\t%s\t%s\t%s\t%s\t0\t8000\n' \
    "$CONTACT_ID" "$LAST" "$FIRST" "$RIGHT_LETTER" "$RIGHT_DIR" >>"$ONE"
fi

echo ">>> NEED one-liner:"
cat "$ONE"
echo

mkdir -p "$right"
export NEED="$ONE"
export LIMIT=1
export EXECUTE=1
cd "$REPO"
bash "$REPO/scripts/BATCH-gulp-to-aid-pipeline.sh"

echo
echo "Fertig. Prüfen:"
echo "  ls -la $right/neu/cv/"
echo "  ls -la $wrong/neu/cv/ 2>/dev/null || echo '(falsch leer — gut)'"
