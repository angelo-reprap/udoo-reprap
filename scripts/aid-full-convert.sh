#!/usr/bin/env bash
# AID Full Convert — alle Letter-Buckets → DB + neu/cv (HTML/DOCX/PDF)
#
# Features:
#   - Resume: überspringt Dirs die schon AID-*.pdf in neu/cv haben
#   - Disk-Guard: pausiert/stoppt wenn freier Speicher unter MIN_FREE_GB
#   - Rework-Liste: Import-Fails, kein PDF, nur HTML, Compare unter Threshold
#   - State-Datei: Fortschritt überlebt Neustart
#   - Sync-Import pro Profil (stabiler als Celery-Flood)
#
# PuTTY/SSH: NICHT im Vordergrund — immer detach:
#   bash scripts/aid-full-convert-detach.sh
#   bash scripts/aid-full-convert-detach.sh --status
#   bash scripts/aid-full-convert-detach.sh --stop
#
# Smoke (2 Profile, ein Letter):
#   LETTERS=bbb LIMIT=2 DRY_RUN=0 bash scripts/aid-full-convert.sh
#
# Alles (aaa…zzz + zzzSONSTIGES), Resume:
#   bash scripts/aid-full-convert-detach.sh
#
# Env:
#   LETTERS=bbb,ccc          nur diese Buckets (default: alle unter AID_profile)
#   SKIP_EXISTING_NEU=1      default 1
#   SKIP_DIRS=a,b            Komma-Liste überspringen
#   MIN_FREE_GB=15           Stop wenn weniger frei auf AID_profile-FS
#   MIN_FREE_GB_REPO=5       Stop wenn Repo/artifacts-FS eng
#   WAVE=25                  nach N Imports kurzen Pause (RAM/OnlyOffice)
#   WAVE_SLEEP_SEC=30
#   COMPARE=1                nach Import leichten Compare (langsamer)
#   COMPARE_MIN_SCORE=80     darunter → rework
#   LIMIT=0                  0=alle; Smoke z.B. 2
#   DEPLOY_FIX=1             Publish-XML-Fix vor Start deployen
#   STATE_DIR=artifacts/aid-full-convert-state
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"
STATE_DIR="${STATE_DIR:-$REPO/artifacts/aid-full-convert-state}"
RUN_ID="${RUN_ID:-$(date +%Y%m%d-%H%M%S)}"
OUT="${OUT:-$STATE_DIR/run-$RUN_ID}"
LOG="${LOG:-$OUT/full-convert.log}"

SKIP_EXISTING_NEU="${SKIP_EXISTING_NEU:-1}"
SKIP_DIRS="${SKIP_DIRS:-}"
MIN_FREE_GB="${MIN_FREE_GB:-15}"
MIN_FREE_GB_REPO="${MIN_FREE_GB_REPO:-5}"
WAVE="${WAVE:-25}"
WAVE_SLEEP_SEC="${WAVE_SLEEP_SEC:-30}"
COMPARE="${COMPARE:-0}"
COMPARE_MIN_SCORE="${COMPARE_MIN_SCORE:-80}"
LIMIT="${LIMIT:-0}"
DRY_RUN="${DRY_RUN:-0}"
DEPLOY_FIX="${DEPLOY_FIX:-1}"
LETTERS="${LETTERS:-}"   # leer = alle 3-letter dirs + zzzSONSTIGES

mkdir -p "$OUT" "$STATE_DIR"
# Append-Log (robuster unter nohup)
exec >>"$LOG" 2>&1

echo "======== AID Full Convert ========"
echo "Start: $(date -Iseconds) host=$(hostname) pid=$$"
echo "ROOT=$ROOT REPO=$REPO OUT=$OUT"
echo "SKIP_EXISTING_NEU=$SKIP_EXISTING_NEU MIN_FREE_GB=$MIN_FREE_GB WAVE=$WAVE COMPARE=$COMPARE LIMIT=$LIMIT"
echo "LETTERS=${LETTERS:-ALL} SKIP_DIRS=${SKIP_DIRS:-(none)}"
echo

cd "$REPO"

# --- helpers ---
_free_gb() {
  local path="$1"
  df -BG --output=avail "$path" 2>/dev/null | tail -1 | tr -dc '0-9' || echo 0
}

_disk_ok() {
  local free_aid free_repo
  free_aid="$(_free_gb "$ROOT")"
  free_repo="$(_free_gb "$REPO")"
  echo "Disk: AID_profile=${free_aid}G free | repo=${free_repo}G free (min ${MIN_FREE_GB}/${MIN_FREE_GB_REPO})"
  if [[ "${free_aid:-0}" -lt "$MIN_FREE_GB" ]]; then
    echo "STOP: zu wenig Platz auf AID_profile (< ${MIN_FREE_GB}G)" >&2
    return 1
  fi
  if [[ "${free_repo:-0}" -lt "$MIN_FREE_GB_REPO" ]]; then
    echo "STOP: zu wenig Platz auf Repo/artifacts (< ${MIN_FREE_GB_REPO}G)" >&2
    return 1
  fi
  return 0
}

_list_letters() {
  if [[ -n "$LETTERS" ]]; then
    echo "$LETTERS" | tr ',;' ' ' 
    return
  fi
  # aaa, bbb, … + ggf. zzzSONSTIGES
  find "$ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null \
    | awk '/^[a-z]{3}$/ || $0=="zzzSONSTIGES"' | sort
}

_newest_orig_pdf() {
  local person_dir="$1"
  find "$person_dir" -maxdepth 1 -type f -iname 'AID-*.pdf' \
    ! -iname '*engl*' ! -iname '*_en.*' ! -iname '*-en.*' \
    ! -iname '*_alt*' ! -iname '*löschen*' ! -iname '*loeschen*' \
    -printf '%T@\t%p\n' 2>/dev/null \
    | sort -nr | head -1 | cut -f2- || true
}

_has_neu_pdf() {
  local person_dir="$1"
  find "$person_dir/neu/cv" -maxdepth 1 -type f -iname 'AID-*.pdf' -print -quit 2>/dev/null || true
}

_neu_inventory() {
  # html/docx/pdf presence for rework classification
  local neu="$1/neu/cv"
  local has_html=0 has_docx=0 has_pdf=0
  [[ -d "$neu" ]] || { echo "none"; return; }
  find "$neu" -maxdepth 1 -type f -iname 'AID-*.html' -print -quit 2>/dev/null | grep -q . && has_html=1 || true
  find "$neu" -maxdepth 1 -type f -iname 'AID-*.docx' -print -quit 2>/dev/null | grep -q . && has_docx=1 || true
  find "$neu" -maxdepth 1 -type f -iname 'AID-*.pdf'  -print -quit 2>/dev/null | grep -q . && has_pdf=1 || true
  echo "html=$has_html;docx=$has_docx;pdf=$has_pdf"
}

# --- deploy publish fix (optional) ---
if [[ "$DEPLOY_FIX" == "1" ]]; then
  _live_wg="/opt/abpe/backend/apps/cv_extractor/generator/word/word_generator.py"
  if grep -q '_xml_safe' "$_live_wg" 2>/dev/null; then
    echo ">>> Deploy Publish-XML-Fix: bereits live (_xml_safe) — skip"
  else
    _deploy="$REPO/scripts/deploy-aid-publish-xml-fix.sh"
    if [[ -f "$_deploy" ]]; then
      chmod +x "$_deploy" 2>/dev/null || true
      echo ">>> Deploy Publish-XML-Fix"
      bash "$_deploy" || echo "WARN: deploy-fix fehlgeschlagen"
    else
      echo "WARN: deploy-aid-publish-xml-fix.sh fehlt — Live-Code unverändert"
    fi
  fi
  echo
fi

# --- build global candidate list ---
CAND="$OUT/candidates.tsv"
: > "$CAND"
DONE="$OUT/done.tsv"
FAIL="$OUT/failures.tsv"
REWORK="$OUT/rework.tsv"
PROGRESS="$OUT/progress.txt"
: > "$DONE"
echo -e "letter\tdir\treason\tdetail" > "$FAIL"
echo -e "letter\tdir\treason\tdetail" > "$REWORK"

skip_neu=0
skip_dirs_n=0
echo "=== Scan $ROOT ==="
for letter in $(_list_letters); do
  letter_dir="$ROOT/$letter"
  [[ -d "$letter_dir" ]] || continue
  for person_dir in "$letter_dir"/*; do
    [[ -d "$person_dir" ]] || continue
    dir="$(basename "$person_dir")"
    case "$dir" in
      neu|audit|ada|Neuer\ Ordner*) continue ;;
    esac
    if [[ -n "$SKIP_DIRS" && ",${SKIP_DIRS}," == *",${dir},"* ]]; then
      skip_dirs_n=$((skip_dirs_n + 1))
      continue
    fi
    if [[ "$SKIP_EXISTING_NEU" == "1" ]]; then
      if [[ -n "$(_has_neu_pdf "$person_dir")" ]]; then
        skip_neu=$((skip_neu + 1))
        continue
      fi
    fi
    pdf="$(_newest_orig_pdf "$person_dir")"
    [[ -n "$pdf" && -f "$pdf" ]] || continue
    # already incomplete neu/cv → mark rework candidate but still try convert
    inv="$(_neu_inventory "$person_dir")"
    if [[ "$inv" == html=1\;docx=0\;pdf=0 || "$inv" == html=1\;docx=1\;pdf=0 ]]; then
      echo -e "${letter}\t${dir}\tincomplete_neu\t${inv}" >> "$REWORK"
    fi
    printf '%s\t%s\t%s\n' "$letter" "$dir" "$pdf" >> "$CAND"
  done
done

total="$(wc -l < "$CAND" | tr -d ' ')"
echo "Übersprungen (neu/cv PDF): $skip_neu"
echo "Übersprungen (SKIP_DIRS):  $skip_dirs_n"
echo "Kandidaten: $total"
if [[ "$LIMIT" -gt 0 && "$total" -gt 0 ]]; then
  head -n "$LIMIT" "$CAND" > "$CAND.lim"
  mv "$CAND.lim" "$CAND"
  total="$(wc -l < "$CAND" | tr -d ' ')"
  echo "LIMIT → $total Profile"
fi

{
  echo "run_id=$RUN_ID"
  echo "started=$(date -Iseconds)"
  echo "candidates=$total"
  echo "skip_neu=$skip_neu"
  echo "pid=$$"
  echo "out=$OUT"
} > "$STATE_DIR/latest.env"
# Kein Symlink: CIFS/SMB unter /mnt/public unterstützt oft keine ln -s
echo "$OUT" > "$STATE_DIR/latest-path.txt"
rm -rf "$STATE_DIR/latest" 2>/dev/null || true
mkdir -p "$STATE_DIR/latest"
# Pointer-Dateien statt Symlink (Status-Script liest latest/ + latest-path)
printf '%s\n' "$OUT" > "$STATE_DIR/latest/OUT_PATH"
# Fortschritt/Listen als relative Kopien der Pfade (Status liest aus OUT direkt via path)
cp -f "$STATE_DIR/latest.env" "$STATE_DIR/latest/latest.env" 2>/dev/null || true

if [[ "$total" -lt 1 ]]; then
  echo "Nichts zu tun (alle haben neu/cv oder keine PDFs)."
  echo "Ende: $(date -Iseconds)"
  exit 0
fi

if [[ "$DRY_RUN" == "1" ]]; then
  echo "DRY_RUN=1 — Manifest:"
  column -t -s $'\t' "$CAND" | head -50
  echo "… ($total Zeilen) → $CAND"
  exit 0
fi

_disk_ok || {
  echo "Abbruch vor Start wegen Disk."
  exit 2
}

# --- activate venv once ---
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate

ok_n=0
fail_n=0
n=0

echo
echo "=== Import (sync, resume-fähig) ==="
while IFS=$'\t' read -r letter dir pdf; do
  [[ -n "$letter" && -n "$dir" ]] || continue
  n=$((n + 1))
  echo
  echo ">>> [$n/$total] $letter/$dir"
  echo "ok=$ok_n fail=$fail_n n=$n/$total $(date -Iseconds)" > "$PROGRESS"

  if ! _disk_ok; then
    echo -e "${letter}\t${dir}\tdisk_full\tpaused_before_import" >> "$FAIL"
    echo "STOP bei Disk-Guard — State bleibt, später einfach neu starten (Resume)."
    break
  fi

  if ! python3 manage.py import_aid_profiles \
      --letter "$letter" --dir "$dir" \
      --sync --no-skip-existing; then
    echo -e "${letter}\t${dir}\timport_fail\tmanage_exit" >> "$FAIL"
    fail_n=$((fail_n + 1))
    continue
  fi

  person="$ROOT/$letter/$dir"
  neu_pdf="$(_has_neu_pdf "$person")"
  inv="$(_neu_inventory "$person")"
  if [[ -z "$neu_pdf" ]]; then
    echo -e "${letter}\t${dir}\tno_neu_pdf\t${inv}" >> "$FAIL"
    echo -e "${letter}\t${dir}\tno_neu_pdf\t${inv}" >> "$REWORK"
    fail_n=$((fail_n + 1))
    continue
  fi

  # docx fehlt oft = Word-Bug → trotzdem PDF ok zählt als OK, aber rework-Hinweis
  if [[ "$inv" != *docx=1* ]]; then
    echo -e "${letter}\t${dir}\tno_docx\t${inv}" >> "$REWORK"
  fi

  score=""
  if [[ "$COMPARE" == "1" ]]; then
    cmp_out="$OUT/compare/${letter}_${dir}"
    mkdir -p "$cmp_out"
    if python3 manage.py compare_aid_neu_cv \
        --letter "$letter" --dir "$dir" --out "$cmp_out" 2>/dev/null; then
      idx="$cmp_out/index.json"
      if [[ -f "$idx" ]]; then
        score="$(python3 - <<PY
import json
from pathlib import Path
p=Path("$idx")
data=json.loads(p.read_text(encoding="utf-8"))
rows=data if isinstance(data,list) else data.get("rows") or data.get("results") or ([data] if isinstance(data,dict) else [])
for r in rows:
    s=r.get("score")
    if s is not None:
        print(s); break
PY
)"
      fi
    fi
    if [[ -n "$score" ]]; then
      # score kann float sein
      low="$(python3 -c "print(1 if float('$score') < float('$COMPARE_MIN_SCORE') else 0)" 2>/dev/null || echo 0)"
      if [[ "$low" == "1" ]]; then
        echo -e "${letter}\t${dir}\tlow_score\tscore=${score};min=${COMPARE_MIN_SCORE}" >> "$REWORK"
      fi
    fi
  fi

  echo -e "${letter}\t${dir}\tOK\t${neu_pdf}\t${inv}\t${score}" >> "$DONE"
  ok_n=$((ok_n + 1))
  echo "OK: $letter/$dir → $neu_pdf ${score:+score=$score}"

  if [[ "$WAVE" -gt 0 && $((n % WAVE)) -eq 0 && "$n" -lt "$total" ]]; then
    echo "--- Wave-Pause ${WAVE_SLEEP_SEC}s (n=$n) ---"
    sleep "$WAVE_SLEEP_SEC"
  fi
done < "$CAND"

# --- summary ---
{
  echo
  echo "======== FERTIG / PAUSE ========"
  echo "Ende: $(date -Iseconds)"
  echo "OK:      $ok_n"
  echo "FAIL:    $fail_n"
  echo "DONE:    $DONE"
  echo "FAILS:   $FAIL"
  echo "REWORK:  $REWORK"
  echo "LOG:     $LOG"
  echo "Resume:  SKIP_EXISTING_NEU=1 bash $REPO/scripts/aid-full-convert-detach.sh"
  _disk_ok || true
} | tee "$OUT/summary.txt"

# compact rework report (unique dirs)
python3 - <<'PY' "$REWORK" "$OUT/rework-summary.txt" 2>/dev/null || true
import sys
from collections import Counter
src, dst = sys.argv[1], sys.argv[2]
c = Counter()
rows = []
with open(src, encoding="utf-8") as f:
    next(f, None)
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 3:
            continue
        letter, d, reason = parts[0], parts[1], parts[2]
        c[reason] += 1
        rows.append((letter, d, reason, parts[3] if len(parts) > 3 else ""))
with open(dst, "w", encoding="utf-8") as out:
    out.write("=== Rework Summary ===\n")
    for k, v in c.most_common():
        out.write(f"  {k}: {v}\n")
    out.write("\n=== Entries ===\n")
    for r in rows:
        out.write("\t".join(r) + "\n")
print("rework-summary →", dst)
PY

echo "ok=$ok_n fail=$fail_n finished=$(date -Iseconds)" >> "$STATE_DIR/latest.env"
exit 0
