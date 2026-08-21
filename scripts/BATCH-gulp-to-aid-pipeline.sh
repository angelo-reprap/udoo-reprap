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
# Throttle (Default):
#   - RAM (used vs Available) ≥ MEM_THRESH (88%) → sleep
#   - CPU (1-min load / nproc) ≥ CPU_THRESH (88%) → sleep
#   - Swap allein blockiert NICHT mehr (voller alter Swap + freier neuer Swap)
#   - Swap nur wenn Swap≥SWAP_THRESH UND RAM≥SWAP_MEM_COMBO (Druck echt)
#   - oder MemAvailable < MIN_AVAIL_MB
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
MEM_THRESH="${MEM_THRESH:-88}"         # % RAM belegt (Total-Available)
CPU_THRESH="${CPU_THRESH:-88}"         # % Load/nproc
SWAP_THRESH="${SWAP_THRESH:-95}"       # % Swap — nur mit RAM-Druck
SWAP_MEM_COMBO="${SWAP_MEM_COMBO:-75}" # Swap-Block nur wenn mem ≥ diesem Wert
MIN_AVAIL_MB="${MIN_AVAIL_MB:-1536}"   # harte Untergrenze freier RAM
THROTTLE_SLEEP="${THROTTLE_SLEEP:-30}"
PAUSE_BETWEEN="${PAUSE_BETWEEN:-2}"  # kurze Pause zwischen Jobs (s)
RUN_INVENTORY="${RUN_INVENTORY:-0}"  # 1 = vorher INVENTORY-gulp-vs-neu-cv.sh
# Optional: exportierte gulp_profil_c (vermeidet CRM-DB unter Last)
# z.B. GULP_TXT_ROOT=/tmp/gulp-batch-…/source-txt
GULP_TXT_ROOT="${GULP_TXT_ROOT:-}"
PDF_WAIT_SECS="${PDF_WAIT_SECS:-15}"  # CIFS: auf Convert-PDF warten

mkdir -p "$OUT_LOG"
exec > >(tee -a "$OUT_LOG/batch.log") 2>&1

echo "======== BATCH gulp → AID Pipeline ========"
echo "Start: $(date -Iseconds) host=$(hostname) pid=$$"
echo "LIMIT=$LIMIT EXECUTE=$EXECUTE MEM_THRESH=$MEM_THRESH CPU_THRESH=$CPU_THRESH"
echo "SWAP_THRESH=$SWAP_THRESH SWAP_MEM_COMBO=$SWAP_MEM_COMBO MIN_AVAIL_MB=$MIN_AVAIL_MB"
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

mem_avail_mb() {
  awk '/MemAvailable:/{printf "%d", $2/1024}' /proc/meminfo
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

# 0 = ok weiter, 1 = drosseln
throttle_should_wait() {
  local mem="$1" cpu="$2" swap="$3" avail="$4"
  local reasons=()
  if (( mem >= MEM_THRESH )); then
    reasons+=("mem=${mem}%≥${MEM_THRESH}")
  fi
  if (( cpu >= CPU_THRESH )); then
    reasons+=("cpu=${cpu}%≥${CPU_THRESH}")
  fi
  if (( avail < MIN_AVAIL_MB )); then
    reasons+=("avail=${avail}MB<${MIN_AVAIL_MB}")
  fi
  # Swap nur bei gleichzeitigem RAM-Druck
  if (( swap >= SWAP_THRESH && mem >= SWAP_MEM_COMBO )); then
    reasons+=("swap=${swap}%≥${SWAP_THRESH}+mem≥${SWAP_MEM_COMBO}")
  fi
  if ((${#reasons[@]} > 0)); then
    printf '%s' "${reasons[*]}"
    return 0
  fi
  return 1
}

throttle_wait() {
  local mem cpu swap avail rounds=0 why
  while true; do
    mem="$(mem_used_pct)"
    cpu="$(cpu_load_pct)"
    swap="$(swap_used_pct)"
    avail="$(mem_avail_mb)"
    if why="$(throttle_should_wait "$mem" "$cpu" "$swap" "$avail")"; then
      rounds=$((rounds + 1))
      echo "THROTTLE ${why} (swap=${swap}% avail=${avail}MB) → sleep ${THROTTLE_SLEEP}s (#${rounds})"
      sleep "$THROTTLE_SLEEP"
      if (( rounds >= 120 )); then
        echo "FAIL: Throttle >120 Runden — Abbruch (Ressourcen bleiben hoch)" >&2
        return 1
      fi
      continue
    fi
    if (( rounds > 0 )); then
      echo "THROTTLE clear mem=${mem}% cpu=${cpu}% swap=${swap}% avail=${avail}MB (after ${rounds} waits)"
    fi
    return 0
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

# letter/dir absichern (CRM-Namen = Quelle der Wahrheit; fs_dir nur wenn passend)
normalize_person_path() {
  python3 - "$1" "$2" "$3" "$4" <<'PY'
import re, sys
letter, dname, last, first = sys.argv[1:5]
umlaut = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})

def slug(last, first):
    raw = f"{last}_{first}".strip("_").lower().translate(umlaut)
    return re.sub(r"[^\w\-]+", "_", raw, flags=re.UNICODE).strip("_") or "unknown"

def bucket(dir_name, last_name=""):
    cdir = (dir_name or "").strip()
    src = cdir.split("_", 1)[0] if "_" in cdir else ((last_name or "").strip() or cdir)
    ch = ""
    for c in src.lower():
        if "a" <= c <= "z":
            ch = c
            break
        if c in "äöüß":
            ch = {"ä": "a", "ö": "o", "ü": "u", "ß": "s"}[c]
            break
    return (ch * 3) if ch else "zzzSONSTIGES"

expected = slug(last, first) if last and first else ""
last_slug = re.sub(r"[^\w\-]+", "_", (last or "").lower().translate(umlaut)).strip("_")

# kaputt/leer → CRM-Slug
if (not dname) or re.fullmatch(r"\d+", dname) or ("_" not in dname and last and first):
    dname = expected or dname

# fs_dir widerspricht CRM-Nachnamen (z.B. bernd_www statt wolfsegger_bernd)
if expected and dname and dname != expected and last_slug:
    if last_slug not in dname.lower():
        print(
            f"WARN path override fs_dir={dname!r} → CRM {expected!r} "
            f"(last={last!r} first={first!r})",
            file=sys.stderr,
        )
        dname = expected

if not re.fullmatch(r"(?:sch|[a-z]{3}|zzzSONSTIGES)", letter or ""):
    letter = bucket(dname, last)
# Letter an CRM-Nachnamen anpassen wenn Dir neu aus CRM kommt
if expected and dname == expected:
    letter = bucket(dname, last)

print(f"{letter}\t{dname}")
PY
}

# Skip header, iterate (leerer gulp_id behält seine Spalte)
while IFS=$'\t' read -r cat contact_id gulp_id last first fs_letter fs_dir has_neu profil_len rest || [[ -n "${cat:-}" ]]; do
  [[ "${cat:-}" == "cat" || -z "${cat:-}" ]] && continue
  # Inventur: fs_dir_no_neu | no_fs_dir | need (manuell)
  case "$cat" in
    fs_dir_no_neu|no_fs_dir|need) ;;
    *) continue ;;
  esac

  # Spalten-Shift-Heilung: gulp_id=Nachname, last=Vorname, first=letter, fs_letter=dir, fs_dir=0/has_neu
  if [[ -n "$gulp_id" && ! "$gulp_id" =~ ^[0-9]+$ && "$first" =~ ^(sch|[a-z]{3})$ ]]; then
    echo "WARN TSV-Shift contact_id=$contact_id: gulp_id=$gulp_id last=$last first=$first → repair"
    profil_len="${has_neu:-$profil_len}"
    has_neu="${fs_dir:-0}"
    fs_dir="$fs_letter"
    fs_letter="$first"
    first="$last"
    last="$gulp_id"
    gulp_id=""
  fi

  if [[ -z "$last" || "$last" =~ ^[0-9]+$ ]]; then
    echo "WARN skip bad TSV row contact_id=$contact_id last=$last dir=$fs_dir"
    continue
  fi
  path_norm="$(normalize_person_path "${fs_letter}" "${fs_dir}" "${last}" "${first}")"
  letter="${path_norm%%$'\t'*}"
  dname="${path_norm#*$'\t'}"
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
  echo "─── [$n] $letter/$dname (gulp_id=${gulp_id:-∅} len=$profil_len) ───"
  throttle_wait || { fail=$((fail+1)); break; }

  if [[ "$EXECUTE" != "1" ]]; then
    ok=$((ok + 1))
    echo "DRY would process $letter/$dname"
    echo -e "DRY\t$contact_id\t$gulp_id\t$letter\t$dname\t\tplan\t0" >>"$RESULT_TSV"
    continue
  fi

  t0=$(date +%s)
  # 1) PDF erzeugen (CONVERT, eine Zeile NEED) — leerer gulp_id als echte leere Spalte
  ONE_NEED="$OUT_LOG/one_${dname}.tsv"
  {
    echo -e "cat\tcontact_id\tgulp_id\tlast\tfirst\tfs_letter\tfs_dir\thas_neu_pdf\tprofil_len"
    printf 'fs_dir_no_neu\t%s\t%s\t%s\t%s\t%s\t%s\t0\t%s\n' \
      "$contact_id" "$gulp_id" "$last" "$first" "$letter" "$dname" "$profil_len"
  } >"$ONE_NEED"

  if ! NEED="$ONE_NEED" LIMIT=1 EXECUTE=1 SKIP_PERSON_DIR=0 \
      OUT_DIR="" VERSION_TAG="$VERSION_TAG" MIN_LEN="$MIN_LEN" \
      GULP_TXT_ROOT="$GULP_TXT_ROOT" \
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

  # Letter/PDF aus Convert-Result (sch vs sss, EBUSY-Rename, …)
  conv_letter="$letter"
  conv_pdf=""
  conv_tsv="$OUT_LOG/convert-$dname/result.tsv"
  if [[ -f "$conv_tsv" ]]; then
    # status contact_id letter dir pdf …
    IFS=$'\t' read -r _cstat _ccid conv_letter _cdir conv_pdf _crest < <(
      tail -n +2 "$conv_tsv" | awk -F'\t' '$1=="OK"{print; exit}'
    ) || true
    [[ -n "${conv_letter:-}" ]] || conv_letter="$letter"
  fi
  person="$AID_ROOT/$conv_letter/$dname"
  neu="$person/neu/cv"

  # Auf Quell-PDF warten (CIFS-Sichtbarkeit nach mkdir/write)
  pdf_src=""
  for ((w = 0; w < PDF_WAIT_SECS; w++)); do
    if [[ -n "$conv_pdf" && -f "$person/$conv_pdf" ]]; then
      pdf_src="$person/$conv_pdf"
      break
    fi
    pdf_src="$(find "$person" -maxdepth 1 -type f -iname 'AID-*.pdf' 2>/dev/null | head -1 || true)"
    [[ -n "$pdf_src" ]] && break
    sleep 1
  done
  if [[ -z "$pdf_src" ]]; then
    fail=$((fail + 1))
    echo "FAIL no source PDF after convert $conv_letter/$dname (waited ${PDF_WAIT_SECS}s)"
    echo -e "FAIL\t$contact_id\t$gulp_id\t$conv_letter\t$dname\t\tno_source_pdf\t$(( $(date +%s) - t0 ))" >>"$RESULT_TSV"
    sleep "$PAUSE_BETWEEN"
    continue
  fi
  echo "Convert-PDF: $pdf_src (letter=$conv_letter)"

  # 2) Import Pipeline (sync) — Letter = Convert-Ablage
  throttle_wait || true
  if ! python3 manage.py import_aid_profiles \
      --letter "$conv_letter" \
      --dir "$dname" \
      --sync \
      --no-skip-existing
  then
    fail=$((fail + 1))
    echo -e "FAIL\t$contact_id\t$gulp_id\t$conv_letter\t$dname\t\timport\t$(( $(date +%s) - t0 ))" >>"$RESULT_TSV"
    echo "FAIL import $dname"
    sleep "$PAUSE_BETWEEN"
    continue
  fi

  secs=$(( $(date +%s) - t0 ))
  pdf_out="$(find "$neu" -maxdepth 1 -type f -iname 'AID-*.pdf' 2>/dev/null | head -1 || true)"
  if [[ -n "$pdf_out" ]]; then
    ok=$((ok + 1))
    echo "OK $conv_letter/$dname → $(basename "$pdf_out") (${secs}s)"
    echo -e "OK\t$contact_id\t$gulp_id\t$conv_letter\t$dname\t$(basename "$pdf_out")\tok\t$secs" >>"$RESULT_TSV"
  else
    fail=$((fail + 1))
    echo "FAIL no neu/cv pdf $dname after import (looked in $neu)"
    echo -e "FAIL\t$contact_id\t$gulp_id\t$conv_letter\t$dname\t\tno_neu_cv\t$secs" >>"$RESULT_TSV"
  fi

  throttle_wait || true
  sleep "$PAUSE_BETWEEN"
done < <(tail -n +2 "$NEED" || true)

python3 - <<PY
import json
from datetime import datetime
from pathlib import Path
summary = {
  "ok": $ok,
  "fail": $fail,
  "skip": $skip,
  "limit": int("$LIMIT" or 0),
  "need": "$NEED",
  "mem_thresh": int("$MEM_THRESH"),
  "cpu_thresh": int("$CPU_THRESH"),
  "throttle_sleep": int("$THROTTLE_SLEEP"),
  "ended": datetime.now().isoformat(timespec="seconds"),
}
Path("$OUT_LOG/summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))
PY

echo
echo "======== FERTIG ok=$ok fail=$fail skip=$skip ========"
echo "Log: $OUT_LOG/batch.log"
echo "TSV: $RESULT_TSV"
