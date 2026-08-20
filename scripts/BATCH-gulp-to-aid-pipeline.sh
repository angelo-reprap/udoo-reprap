#!/usr/bin/env bash
# Gulp CRM → Cleaner → AID-PDF → Pipeline → neu/cv
# Nur Kontakte OHNE bestehendes neu/cv (NEED / fs_dir_no_neu).
#
# 10er-Test auf ucs5:
#   cd /mnt/public/udoo-reprap && git pull origin cursor/gulp-keyword-pipeline-1532
#   LIMIT=10 bash scripts/BATCH-gulp-to-aid-pipeline.sh
#
# Overnight (detached):
#   LIMIT=0 bash scripts/BATCH-gulp-to-aid-detach.sh
#
# Throttle (Default): bei RAM≥88% oder CPU≥88% → sleep THROTTLE_SLEEP (30s), bis darunter.
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
AID_ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"
NEED="${NEED:-}"
LIMIT="${LIMIT:-10}"
EXECUTE="${EXECUTE:-1}"          # 0 = nur planen
SKIP_EXISTING_NEU="${SKIP_EXISTING_NEU:-1}"
VERSION_TAG="${VERSION_TAG:-1.0.0.0}"
MIN_LEN="${MIN_LEN:-200}"
OUT_LOG="${OUT_LOG:-/tmp/gulp-batch-$(date +%Y%m%d-%H%M%S)}"
MEM_THRESH="${MEM_THRESH:-88}"   # % genutzter RAM (ohne Available)
CPU_THRESH="${CPU_THRESH:-88}"   # % aus 1-min Load / nproc
THROTTLE_SLEEP="${THROTTLE_SLEEP:-30}"
PAUSE_BETWEEN="${PAUSE_BETWEEN:-2}"  # kurze Pause zwischen Jobs (s)
RUN_INVENTORY="${RUN_INVENTORY:-0}"  # 1 = vorher INVENTORY-gulp-vs-neu-cv.sh

mkdir -p "$OUT_LOG"
exec > >(tee -a "$OUT_LOG/batch.log") 2>&1

echo "======== BATCH gulp → AID Pipeline ========"
echo "Start: $(date -Iseconds) host=$(hostname) pid=$$"
echo "LIMIT=$LIMIT EXECUTE=$EXECUTE MEM_THRESH=$MEM_THRESH CPU_THRESH=$CPU_THRESH"
echo "THROTTLE_SLEEP=$THROTTLE_SLEEP PAUSE_BETWEEN=$PAUSE_BETWEEN"
echo "OUT_LOG=$OUT_LOG"
echo

# ── Ressourcen ──────────────────────────────────────────────────────────────
mem_used_pct() {
  awk '/MemTotal:/{t=$2} /MemAvailable:/{a=$2} END{
    if (t+0<1) {print 100; exit}
    printf "%d", (t-a)*100/t
  }' /proc/meminfo
}

cpu_load_pct() {
  local n load
  n="$(nproc 2>/dev/null || echo 1)"
  load="$(awk '{print $1}' /proc/loadavg)"
  python3 -c "print(int(round(float('$load')/max(float('$n'),1.0)*100)))" 2>/dev/null || echo 0
}

swap_used_pct() {
  awk '/SwapTotal:/{t=$2} /SwapFree:/{f=$2} END{
    if (t+0<1) {print 0; exit}
    printf "%d", (t-f)*100/t
  }' /proc/meminfo
}

throttle_wait() {
  local mem cpu swap rounds=0
  while true; do
    mem="$(mem_used_pct)"
    cpu="$(cpu_load_pct)"
    swap="$(swap_used_pct)"
    if (( mem < MEM_THRESH && cpu < CPU_THRESH && swap < 95 )); then
      if (( rounds > 0 )); then
        echo "THROTTLE clear mem=${mem}% cpu=${cpu}% swap=${swap}% (after ${rounds} waits)"
      fi
      return 0
    fi
    rounds=$((rounds + 1))
    echo "THROTTLE mem=${mem}% (lim ${MEM_THRESH}) cpu=${cpu}% (lim ${CPU_THRESH}) swap=${swap}% → sleep ${THROTTLE_SLEEP}s (#${rounds})"
    sleep "$THROTTLE_SLEEP"
    # harte Notbremse: sehr viele Warterunden
    if (( rounds >= 120 )); then
      echo "FAIL: Throttle >120 Runden — Abbruch (Ressourcen bleiben hoch)" >&2
      return 1
    fi
  done
}

# ── NEED TSV ────────────────────────────────────────────────────────────────
if [[ "$RUN_INVENTORY" == "1" ]]; then
  echo ">>> INVENTORY-gulp-vs-neu-cv.sh"
  bash "$REPO/scripts/INVENTORY-gulp-vs-neu-cv.sh" || true
fi

if [[ -z "$NEED" ]]; then
  NEED="$(ls -td /tmp/gulp-vs-neu-*/need_neu_cv_with_fs_dir.tsv 2>/dev/null | head -1 || true)"
fi
if [[ -z "$NEED" || ! -f "$NEED" ]]; then
  echo "FAIL: NEED TSV fehlt. Setze NEED=… oder RUN_INVENTORY=1" >&2
  echo "  Beispiel: RUN_INVENTORY=1 LIMIT=10 bash $0" >&2
  exit 1
fi
echo "NEED=$NEED ($(wc -l <"$NEED") Zeilen inkl. Header)"

cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"
export REPO AID_ROOT NEED OUT_LOG LIMIT EXECUTE SKIP_EXISTING_NEU VERSION_TAG MIN_LEN
export MEM_THRESH CPU_THRESH THROTTLE_SLEEP PAUSE_BETWEEN

# Export throttle helpers for python via env only — bash throttle before each job
RESULT_TSV="$OUT_LOG/result.tsv"
echo -e "status\tcontact_id\tgulp_id\tletter\tdir\tpdf\tnote\tsecs" >"$RESULT_TSV"

ok=0
fail=0
skip=0
n=0

# Skip header, iterate
while IFS=$'\t' read -r cat contact_id gulp_id last first fs_letter fs_dir has_neu profil_len rest || [[ -n "${cat:-}" ]]; do
  [[ "${cat:-}" == "cat" || -z "${cat:-}" ]] && continue
  [[ "$cat" != "fs_dir_no_neu" && "$cat" != "need" ]] && continue
  # TSV columns from inventory: cat contact_id gulp_id last first fs_letter fs_dir has_neu_pdf profil_len
  dname="${fs_dir}"
  letter="${fs_letter}"
  [[ -z "$dname" ]] && continue

  if [[ "$LIMIT" -gt 0 && "$ok" -ge "$LIMIT" ]]; then
    echo "LIMIT $LIMIT erreicht (ok=$ok) — Stop"
    break
  fi
  n=$((n + 1))

  person="$AID_ROOT/$letter/$dname"
  neu="$person/neu/cv"

  if [[ "$SKIP_EXISTING_NEU" == "1" ]] && [[ -d "$neu" ]]; then
    if find "$neu" -maxdepth 1 -type f -iname 'AID-*.pdf' -print -quit 2>/dev/null | grep -q .; then
      skip=$((skip + 1))
      echo "SKIP has_neu_cv $letter/$dname"
      echo -e "SKIP\t$contact_id\t$gulp_id\t$letter\t$dname\t\thas_neu_cv\t0" >>"$RESULT_TSV"
      continue
    fi
  fi

  echo
  echo "─── [$n] $letter/$dname (gulp_id=$gulp_id len=$profil_len) ───"
  throttle_wait || { fail=$((fail+1)); break; }

  if [[ "$EXECUTE" != "1" ]]; then
    ok=$((ok + 1))
    echo "DRY would process $letter/$dname"
    echo -e "DRY\t$contact_id\t$gulp_id\t$letter\t$dname\t\tplan\t0" >>"$RESULT_TSV"
    continue
  fi

  t0=$(date +%s)
  # 1) PDF erzeugen (CONVERT, eine Zeile NEED)
  ONE_NEED="$OUT_LOG/one_${dname}.tsv"
  {
    echo -e "cat\tcontact_id\tgulp_id\tlast\tfirst\tfs_letter\tfs_dir\thas_neu_pdf\tprofil_len"
    echo -e "fs_dir_no_neu\t$contact_id\t$gulp_id\t$last\t$first\t$letter\t$dname\t0\t$profil_len"
  } >"$ONE_NEED"

  if ! NEED="$ONE_NEED" LIMIT=1 EXECUTE=1 SKIP_PERSON_DIR=0 \
      OUT_DIR="" VERSION_TAG="$VERSION_TAG" MIN_LEN="$MIN_LEN" \
      OUT_LOG="$OUT_LOG/convert-$dname" \
      bash "$REPO/scripts/CONVERT-gulp-txt-to-aid-pdf.sh"
  then
    fail=$((fail + 1))
    echo -e "FAIL\t$contact_id\t$gulp_id\t$letter\t$dname\t\tconvert\t$(( $(date +%s) - t0 ))" >>"$RESULT_TSV"
    echo "FAIL convert $dname"
    throttle_wait || true
    sleep "$PAUSE_BETWEEN"
    continue
  fi

  # 2) Import Pipeline (sync)
  throttle_wait || true
  if ! python3 manage.py import_aid_profiles \
      --letter "$letter" \
      --dir "$dname" \
      --sync \
      --no-skip-existing
  then
    fail=$((fail + 1))
    echo -e "FAIL\t$contact_id\t$gulp_id\t$letter\t$dname\t\timport\t$(( $(date +%s) - t0 ))" >>"$RESULT_TSV"
    echo "FAIL import $dname"
    sleep "$PAUSE_BETWEEN"
    continue
  fi

  secs=$(( $(date +%s) - t0 ))
  pdf_out="$(find "$neu" -maxdepth 1 -type f -iname 'AID-*.pdf' 2>/dev/null | head -1 || true)"
  if [[ -n "$pdf_out" ]]; then
    ok=$((ok + 1))
    echo "OK $letter/$dname → $(basename "$pdf_out") (${secs}s)"
    echo -e "OK\t$contact_id\t$gulp_id\t$letter\t$dname\t$(basename "$pdf_out")\tok\t$secs" >>"$RESULT_TSV"
  else
    fail=$((fail + 1))
    echo "FAIL no neu/cv pdf $dname after import"
    echo -e "FAIL\t$contact_id\t$gulp_id\t$letter\t$dname\t\tno_neu_cv\t$secs" >>"$RESULT_TSV"
  fi

  throttle_wait || true
  sleep "$PAUSE_BETWEEN"
done <"$NEED"

summary="$OUT_LOG/summary.json"
python3 - <<PY
import json
print(json.dumps({
  "ok": $ok, "fail": $fail, "skip": $skip,
  "limit": $LIMIT, "need": "$NEED",
  "mem_thresh": $MEM_THRESH, "cpu_thresh": $CPU_THRESH,
  "ended": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
}, indent=2))
PY
echo "$summary"
python3 -c "import json; json.dump({'ok':$ok,'fail':$fail,'skip':$skip,'limit':$LIMIT,'need':'$NEED'}, open('$summary','w'), indent=2)"

echo
echo "======== FERTIG ok=$ok fail=$fail skip=$skip ========"
echo "Log: $OUT_LOG/batch.log"
echo "TSV: $RESULT_TSV"
