#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# SAFE Cleanup — nur die Personen aus EINER gulp-batch result.tsv
# ═══════════════════════════════════════════════════════════════════════════
#
# Löscht NIEMALS:
#   • AID_profile-Root, Letter-Buckets, andere Personen
#   • „alles seit Datum“ / Presets / Wildcard
#   • Person-Stammordner selbst (nur Inhalt: neu/ + Convert-PDF)
#
# Löscht NUR (pro TSV-Zeile OK|FAIL):
#   1) $AID_ROOT/$letter/$dir/neu/          (ganzen neu-Baum)
#   2) $AID_ROOT/$letter/$dir/AID-*_1.0.0.0.pdf  (nur Convert-Quell-PDF)
#   3) optional DB: Consultant/Uploads mit exakt consultant_dir=$dir
#
# Ablauf (ucs5) — IMMER erst Dry-Run:
#
#   RESULT_TSV=/tmp/gulp-batch-20260820-175411/result.tsv \
#     bash scripts/SAFE-CLEANUP-gulp-batch-10.sh
#
#   # Plan prüfen (Pfad-Liste + DB-Treffer). Dann:
#
#   RESULT_TSV=/tmp/gulp-batch-20260820-175411/result.tsv \
#     I_UNDERSTAND=yes EXECUTE=1 DRY_RUN=0 CLEAN_DB=1 \
#     bash scripts/SAFE-CLEANUP-gulp-batch-10.sh
#
# Danach Batch neu:
#   LIMIT=10 bash scripts/BATCH-gulp-to-aid-pipeline.sh
#
set -euo pipefail

AID_ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"
RESULT_TSV="${RESULT_TSV:-}"
EXECUTE="${EXECUTE:-0}"
DRY_RUN="${DRY_RUN:-1}"
CLEAN_DB="${CLEAN_DB:-1}"
I_UNDERSTAND="${I_UNDERSTAND:-}"
MAX_PERSONS="${MAX_PERSONS:-12}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
# Nur diese Zusatz-Pfade (letter/dir), z.B. kaputter 1. Lauf — nie Wildcards
EXTRA_DIRS="${EXTRA_DIRS:-}"

die() { echo "FAIL: $*" >&2; exit 1; }

# ── RESULT_TSV: explizit oder neueste gulp-batch ──────────────────────────
if [[ -z "$RESULT_TSV" ]]; then
  RESULT_TSV="$(ls -td /tmp/gulp-batch-*/result.tsv 2>/dev/null | head -1 || true)"
fi
[[ -n "$RESULT_TSV" && -f "$RESULT_TSV" ]] || die "RESULT_TSV fehlt — bitte setzen"
# Sicherheitsnetz: Standard nur gulp-batch; Mini-TSV mit ALLOW_ANY_TSV=1
case "$RESULT_TSV" in
  */gulp-batch-*/result.tsv) ;;
  *)
    if [[ "${ALLOW_ANY_TSV:-0}" != "1" ]]; then
      die "RESULT_TSV muss …/gulp-batch-…/result.tsv sein (oder ALLOW_ANY_TSV=1): $RESULT_TSV"
    fi
    ;;
esac

# ── Guards ────────────────────────────────────────────────────────────────
[[ -d "$AID_ROOT" ]] || die "AID_ROOT fehlt: $AID_ROOT"
# Bei DELETE nur den echten Share-Root erlauben (kein Versehen mit Testpfad)
if [[ "$EXECUTE" == "1" && "$DRY_RUN" != "1" ]]; then
  case "$AID_ROOT" in
    /mnt/public/Berater/AID_profile|/mnt/public/Berater/AID_profile/) ;;
    *)
      if [[ "${ALLOW_OTHER_AID_ROOT:-0}" != "1" ]]; then
        die "AID_ROOT unerwartet ($AID_ROOT) — DELETE nur auf Share (oder ALLOW_OTHER_AID_ROOT=1)"
      fi
      ;;
  esac
fi

is_safe_letter() {
  [[ "$1" =~ ^(sch|[a-z]{3})$ ]]
}
is_safe_dir() {
  # nachname_vorname (mind. ein Unterstrich), keine Pfadtrenner, keine reinen Zahlen
  local d="$1"
  [[ "$d" =~ ^[a-z0-9][a-z0-9._-]*_[a-z0-9][a-z0-9._-]*$ ]] || return 1
  [[ "$d" != *"/"* && "$d" != *".."* && "$d" != *"*"* ]] || return 1
  [[ ! "$d" =~ ^[0-9]+$ ]] || return 1
  return 0
}

# ── Targets aus TSV sammeln ───────────────────────────────────────────────
declare -a TARGETS=()   # letter/dir
declare -a DIRS_ONLY=() # dir names for DB

add_target() {
  local letter="$1" dir="$2" src="$3"
  is_safe_letter "$letter" || die "unsicherer letter='$letter' ($src)"
  is_safe_dir "$dir" || die "unsicherer dir='$dir' ($src) — erwartet nachname_vorname"
  local key="$letter/$dir"
  local t
  for t in "${TARGETS[@]:-}"; do
    [[ "$t" == "$key" ]] && return 0
  done
  TARGETS+=("$key")
  DIRS_ONLY+=("$dir")
}

while IFS=$'\t' read -r status _contact _gulp letter dir _pdf _note _secs || [[ -n "${status:-}" ]]; do
  [[ "$status" == "status" || -z "$status" ]] && continue
  [[ "$status" != "OK" && "$status" != "FAIL" ]] && continue
  [[ -z "$letter" || -z "$dir" ]] && continue
  add_target "$letter" "$dir" "TSV:$RESULT_TSV"
done <"$RESULT_TSV"

for pair in $EXTRA_DIRS; do
  [[ -z "$pair" ]] && continue
  [[ "$pair" == */* ]] || die "EXTRA_DIRS Eintrag braucht letter/dir (got: $pair)"
  add_target "${pair%%/*}" "${pair#*/}" "EXTRA"
done

n="${#TARGETS[@]}"
[[ "$n" -ge 1 ]] || die "keine Targets in TSV"
[[ "$n" -le "$MAX_PERSONS" ]] || die "zu viele Targets ($n > MAX_PERSONS=$MAX_PERSONS) — Abbruch"

MODE="DRY-RUN"
if [[ "$EXECUTE" == "1" && "$DRY_RUN" != "1" ]]; then
  MODE="DELETE"
fi

echo "════════════════════════════════════════════════════"
echo " SAFE-CLEANUP gulp-batch (max $MAX_PERSONS Personen)"
echo "════════════════════════════════════════════════════"
echo "RESULT_TSV = $RESULT_TSV"
echo "AID_ROOT   = $AID_ROOT"
echo "MODE       = $MODE"
echo "CLEAN_DB   = $CLEAN_DB"
echo "Targets    = $n"
echo

# ── Plan auflisten (immer) ────────────────────────────────────────────────
plan_fs=0
plan_db_dirs=()
i=0
for key in "${TARGETS[@]}"; do
  i=$((i + 1))
  letter="${key%%/*}"
  dir="${key#*/}"
  person="$AID_ROOT/$letter/$dir"
  echo "── [$i/$n] $letter/$dir"
  if [[ ! -d "$person" ]]; then
    echo "  FS: (Ordner fehlt — nichts zu löschen)"
  else
    if [[ -d "$person/neu" ]]; then
      neu_n="$(find "$person/neu" -type f 2>/dev/null | wc -l | tr -d ' ')"
      echo "  FS: rm -rf $person/neu/   ($neu_n Dateien)"
      plan_fs=$((plan_fs + 1))
    else
      echo "  FS: kein neu/"
    fi
    while IFS= read -r f; do
      [[ -z "$f" ]] && continue
      echo "  FS: rm $(basename "$f")   ($(stat -c%s "$f" 2>/dev/null || echo ?) bytes)"
      plan_fs=$((plan_fs + 1))
    done < <(find "$person" -maxdepth 1 -type f \( -iname 'AID-*.pdf' -o -iname 'AID-*.pdf.part' \) 2>/dev/null)
    # Person-Root wird NICHT gelöscht
    echo "  FS: behalte Ordner $person/"
  fi
  plan_db_dirs+=("$dir")
done

echo
echo "DB würde nur diese consultant_dir treffen ($n Stück):"
printf '  • %s\n' "${DIRS_ONLY[@]}"

if [[ "$CLEAN_DB" == "1" ]]; then
  echo
  echo "── DB Dry-Inventar (nur lesen) ──"
  if [[ -d "$BACKEND" ]]; then
    (
      cd "$BACKEND"
      # shellcheck disable=SC1091
      [[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
      # shellcheck disable=SC2086
      set --
      for d in "${DIRS_ONLY[@]}"; do
        set -- "$@" --dir "$d"
      done
      python3 manage.py cleanup_aid_test_imports "$@" --any-source --dry-run 2>&1 | tail -40
    ) || echo "  WARN: DB-Inventar fehlgeschlagen (Backend/venv?)"
  else
    echo "  WARN: BACKEND=$BACKEND fehlt — DB-Schritt übersprungen"
  fi
fi

echo
echo "Zusammenfassung Plan: $n Personen | FS-Aktionen≈$plan_fs | DB=dirs×$n"
echo

# ── Execute nur mit Doppel-Bestätigung ────────────────────────────────────
if [[ "$MODE" != "DELETE" ]]; then
  echo "Dry-run — nichts gelöscht."
  echo
  echo "Zum wirklichen Löschen (nach Plan-Check):"
  echo "  RESULT_TSV=$RESULT_TSV \\"
  echo "    I_UNDERSTAND=yes EXECUTE=1 DRY_RUN=0 CLEAN_DB=$CLEAN_DB \\"
  echo "    bash $0"
  exit 0
fi

[[ "$I_UNDERSTAND" == "yes" ]] || die "EXECUTE ohne I_UNDERSTAND=yes — Abbruch"

echo ">>> LÖSCHE jetzt $n Personen (FS${CLEAN_DB:+ + DB}) …"
echo

for key in "${TARGETS[@]}"; do
  letter="${key%%/*}"
  dir="${key#*/}"
  person="$AID_ROOT/$letter/$dir"
  echo "── DELETE $letter/$dir"
  # Hard re-check vor jedem rm
  is_safe_letter "$letter" || die "abort letter=$letter"
  is_safe_dir "$dir" || die "abort dir=$dir"
  [[ "$person" == "$AID_ROOT/$letter/$dir" ]] || die "path mismatch"
  [[ "$person" != "$AID_ROOT" && "$person" != "$AID_ROOT/" ]] || die "refusing AID_ROOT"
  [[ "$person" != "$AID_ROOT/$letter" && "$person" != "$AID_ROOT/$letter/" ]] || die "refusing letter bucket"

  if [[ -d "$person/neu" ]]; then
    echo "  leere neu/ (Dateien einzeln, dann rmdir)"
    # CIFS: rm -rf kann „Directory not empty“ / busy liefern
    find "$person/neu" -mindepth 1 -depth -print0 2>/dev/null \
      | while IFS= read -r -d '' f; do
          rm -rf "$f" 2>/dev/null \
            || mv -f "$f" "${f}.busy-$(date +%H%M%S)" 2>/dev/null \
            || echo "  WARN: busy/übersprungen: $f"
        done
    rmdir "$person/neu" 2>/dev/null \
      || rm -rf "$person/neu" 2>/dev/null \
      || echo "  WARN: neu/ bleibt (Reste busy) — CONVERT schreibt trotzdem neu"
  fi
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    echo "  rm $f"
    if ! rm -f "$f" 2>/dev/null; then
      busy="${f}.busy-$(date +%H%M%S)"
      if mv -f "$f" "$busy" 2>/dev/null; then
        echo "  WARN: busy → umbenannt $(basename "$busy")"
      else
        echo "  WARN: Device busy, belasse $(basename "$f") — CONVERT weicht auf *_1.0.0.1.pdf aus"
      fi
    fi
  done < <(find "$person" -maxdepth 1 -type f \( -iname 'AID-*.pdf' -o -iname 'AID-*.pdf.part' \) 2>/dev/null)
done

if [[ "$CLEAN_DB" == "1" ]]; then
  echo
  echo "── DB DELETE (nur die $n Dirs, --yes) ──"
  cd "$BACKEND"
  # shellcheck disable=SC1091
  [[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
  set --
  for d in "${DIRS_ONLY[@]}"; do
    set -- "$@" --dir "$d"
  done
  # kein --neu-cv hier: FS haben wir oben gezielt geleert
  # Limit = Personen × 8 (de/en + Alt-Versionen), hart max 96
  db_limit=$(( n * 8 ))
  [[ "$db_limit" -gt 96 ]] && db_limit=96
  python3 manage.py cleanup_aid_test_imports "$@" --any-source --yes --limit "$db_limit"
fi

echo
echo "Fertig. Person-Stammordner bleiben. Neu-Batch:"
echo "  LIMIT=10 bash scripts/BATCH-gulp-to-aid-pipeline.sh"
