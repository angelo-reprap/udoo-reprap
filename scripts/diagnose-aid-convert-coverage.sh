#!/usr/bin/env bash
# Prüft AID-Convert-Vollständigkeit (Filesystem) + Stichprobe Alt vs Neu + DB/ES.
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap
#   LETTERS=ccc-zzz bash scripts/diagnose-aid-convert-coverage.sh
#   LETTERS=aaa,bbb bash scripts/diagnose-aid-convert-coverage.sh
#   SAMPLE=30 COMPARE=1 bash scripts/diagnose-aid-convert-coverage.sh
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
OUT="${OUT:-$REPO/artifacts/aid-coverage-$(date +%Y%m%d-%H%M%S)}"
LETTERS="${LETTERS:-ccc-zzz}"
SAMPLE="${SAMPLE:-20}"          # Compare-Stichprobe pro Letter-Range
COMPARE="${COMPARE:-1}"         # 1 = compare_aid_neu_cv Stichprobe
DB_CHECK="${DB_CHECK:-1}"

mkdir -p "$OUT"
exec > >(tee -a "$OUT/coverage.log") 2>&1

echo "======== AID Convert Coverage ========"
echo "Start: $(date -Iseconds) OUT=$OUT"
echo "LETTERS=$LETTERS SAMPLE=$SAMPLE COMPARE=$COMPARE DB_CHECK=$DB_CHECK"
echo

_expand_letters() {
  local spec="$1"
  if [[ "$spec" == "ccc-zzz" ]]; then
    python3 -c "print(' '.join(c*3 for c in 'cdefghijklmnopqrstuvwxyz'))"
    return
  fi
  if [[ "$spec" == "aaa-zzz" ]]; then
    python3 -c "print(' '.join(c*3 for c in 'abcdefghijklmnopqrstuvwxyz'))"
    return
  fi
  echo "$spec" | tr ',;' ' '
}

MISS="$OUT/missing-neu-cv.tsv"
OKF="$OUT/has-neu-cv.tsv"
: > "$MISS"
: > "$OKF"
echo -e "letter\tdir\torig_pdf" > "$MISS"
echo -e "letter\tdir\tneu_pdf" > "$OKF"

total_dirs=0
with_orig=0
with_neu=0
missing=0

echo "=== Filesystem Scan ==="
for letter in $(_expand_letters "$LETTERS"); do
  letter_dir="$ROOT/$letter"
  [[ -d "$letter_dir" ]] || continue
  l_dirs=0 l_orig=0 l_neu=0 l_miss=0
  for person_dir in "$letter_dir"/*; do
    [[ -d "$person_dir" ]] || continue
    dir="$(basename "$person_dir")"
    case "$dir" in neu|audit|ada|Neuer\ Ordner*) continue ;; esac
    l_dirs=$((l_dirs + 1))
    total_dirs=$((total_dirs + 1))

    orig="$(
      find "$person_dir" -maxdepth 1 -type f -iname 'AID-*.pdf' \
        ! -iname '*engl*' ! -iname '*_en.*' ! -iname '*-en.*' \
        ! -iname '*_alt*' ! -iname '*löschen*' ! -iname '*loeschen*' \
        -printf '%T@\t%p\n' 2>/dev/null \
      | sort -nr | head -1 | cut -f2- || true
    )"
    [[ -n "$orig" && -f "$orig" ]] || continue
    l_orig=$((l_orig + 1))
    with_orig=$((with_orig + 1))

    neu="$(
      find "$person_dir/neu/cv" -maxdepth 1 -type f -iname 'AID-*.pdf' \
        -print -quit 2>/dev/null || true
    )"
    if [[ -n "$neu" && -f "$neu" ]]; then
      l_neu=$((l_neu + 1))
      with_neu=$((with_neu + 1))
      printf '%s\t%s\t%s\n' "$letter" "$dir" "$neu" >> "$OKF"
    else
      l_miss=$((l_miss + 1))
      missing=$((missing + 1))
      printf '%s\t%s\t%s\n' "$letter" "$dir" "$orig" >> "$MISS"
    fi
  done
  pct=0
  [[ "$l_orig" -gt 0 ]] && pct=$((l_neu * 100 / l_orig))
  printf '  %-12s dirs=%-4d orig=%-4d neu=%-4d miss=%-4d (%d%%)\n' \
    "$letter" "$l_dirs" "$l_orig" "$l_neu" "$l_miss" "$pct"
done

echo
echo "=== Summe ==="
echo "Ordner gesamt:     $total_dirs"
echo "Mit Original-PDF:  $with_orig"
echo "Mit neu/cv PDF:    $with_neu"
echo "Fehlend neu/cv:    $missing"
if [[ "$with_orig" -gt 0 ]]; then
  echo "Coverage:          $((with_neu * 100 / with_orig))%"
fi
echo "Missing list:      $MISS"
echo "OK list:           $OKF"

# --- Stichprobe Compare Alt vs Neu ---
if [[ "$COMPARE" == "1" && "$with_neu" -gt 0 ]]; then
  echo
  echo "=== Compare Stichprobe (n<=$SAMPLE) ==="
  cd "$BACKEND"
  # shellcheck disable=SC1091
  [[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate

  SAMPLE_TSV="$OUT/compare-sample.tsv"
  : > "$SAMPLE_TSV"
  echo -e "letter\tdir\tscore\tstatus\tflags" >> "$SAMPLE_TSV"

  # zufällige / gleichmäßige Stichprobe aus OK-Liste
  mapfile -t rows < <(tail -n +2 "$OKF" | shuf | head -n "$SAMPLE")
  n=0
  for row in "${rows[@]}"; do
    IFS=$'\t' read -r letter dir neu <<<"$row"
    [[ -n "$letter" && -n "$dir" ]] || continue
    n=$((n + 1))
    dest="$OUT/compare/${letter}_${dir}"
    mkdir -p "$dest"
    echo ">>> [$n/${#rows[@]}] compare $letter/$dir"
    python3 manage.py compare_aid_neu_cv \
      --letter "$letter" --dir "$dir" --out "$dest" >/dev/null 2>&1 || true
    idx="$dest/index.json"
    if [[ -f "$idx" ]]; then
      python3 - <<PY >> "$SAMPLE_TSV"
import json
from pathlib import Path
p=Path("$idx")
data=json.loads(p.read_text(encoding="utf-8"))
rows=data if isinstance(data,list) else data.get("rows") or data.get("results") or ([data] if isinstance(data,dict) else [])
for r in rows:
    flags=";".join(r.get("flags") or [])
    print(f"$letter\t$dir\t{r.get('score')}\t{r.get('status')}\t{flags}")
    break
else:
    print("$letter\t$dir\t?\tno_row\t")
PY
    else
      echo -e "$letter\t$dir\t?\tno_index\t" >> "$SAMPLE_TSV"
    fi
  done

  echo
  echo "--- Compare Stats ---"
  python3 - <<'PY' "$SAMPLE_TSV"
import sys
from pathlib import Path
p=Path(sys.argv[1])
scores=[]
status={}
for i,line in enumerate(p.read_text(encoding="utf-8").splitlines()):
    if i==0: continue
    parts=line.split("\t")
    if len(parts)<4: continue
    st=parts[3]; status[st]=status.get(st,0)+1
    try:
        scores.append(float(parts[2]))
    except Exception:
        pass
print("samples:", sum(status.values()))
print("status:", dict(sorted(status.items(), key=lambda x:-x[1])))
if scores:
    scores.sort()
    avg=sum(scores)/len(scores)
    def pct(q):
        i=int(round((len(scores)-1)*q))
        return scores[i]
    print(f"score avg={avg:.1f}  p50={pct(0.5):.1f}  p10={pct(0.1):.1f}  min={scores[0]:.1f}  max={scores[-1]:.1f}")
    low=[s for s in scores if s < 80]
    print(f"score < 80: {len(low)} / {len(scores)}")
PY
  echo "Sample TSV: $SAMPLE_TSV"
fi

# --- DB + ES ---
if [[ "$DB_CHECK" == "1" ]]; then
  echo
  echo "=== DB / Index / Skills ==="
  cd "$BACKEND"
  # shellcheck disable=SC1091
  [[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
  export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"
  export PYTHONPATH="${PYTHONPATH:-$BACKEND}"
  python3 - <<'PY'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()

from django.db.models import Count, Avg, Q

out = []
try:
    from apps.cv_extractor.models import Consultant, ConsultantSkill, ConsultantVersion
except Exception as e:
    print('CV models import fail:', e)
    raise SystemExit(0)

c_total = Consultant.objects.count()
c_with_aid = Consultant.objects.exclude(aid__isnull=True).exclude(aid='').count()
print(f'Consultant:           {c_total}')
print(f'Consultant mit AID:   {c_with_aid}')

try:
    v_total = ConsultantVersion.objects.count()
    print(f'ConsultantVersion:    {v_total}')
except Exception as e:
    print('ConsultantVersion:', e)

try:
    sk_total = ConsultantSkill.objects.count()
    sk_cons = ConsultantSkill.objects.values('consultant_id').distinct().count()
    # weight / level fields if present
    fields = {f.name for f in ConsultantSkill._meta.get_fields()}
    print(f'ConsultantSkill rows: {sk_total}')
    print(f'Consultants m. Skills:{sk_cons}')
    if 'weight' in fields:
        agg = ConsultantSkill.objects.aggregate(avg=Avg('weight'))
        print(f'Skill weight avg:     {agg["avg"]}')
    if 'level' in fields:
        print('Skill level values:   ', list(ConsultantSkill.objects.values_list('level', flat=True).distinct()[:15]))
    if 'category' in fields:
        top = list(ConsultantSkill.objects.values('category').annotate(n=Count('id')).order_by('-n')[:8])
        print('Top skill categories: ', top)
except Exception as e:
    print('Skills:', e)

# Sample: recent AIDs that look converted
try:
    recent = list(
        Consultant.objects.exclude(aid='')
        .order_by('-id')[:5]
        .values_list('aid', 'consultant_dir', 'first_name', 'last_name')
    )
    print('Recent consultants:')
    for r in recent:
        print(' ', r)
except Exception as e:
    print('recent:', e)

# ElasticSearch
try:
    from elasticsearch import Elasticsearch
    from django.conf import settings
    hosts = getattr(settings, 'ELASTICSEARCH_DSL', {}).get('default', {}).get('hosts') \
        or getattr(settings, 'ELASTICSEARCH_HOSTS', None) \
        or ['http://localhost:9200']
    if isinstance(hosts, str):
        hosts = [hosts]
    es = Elasticsearch(hosts, verify_certs=False, request_timeout=10)
    info = es.info()
    print(f'ES version:           {info.get("version",{}).get("number")}')
    for idx in ('abpe_skills_index', 'abpe_profile_versions', 'abpe_profiles_v2', 'consultants'):
        try:
            if es.indices.exists(index=idx):
                cnt = es.count(index=idx).get('count')
                print(f'ES index {idx}: {cnt} docs')
        except Exception:
            pass
except Exception as e:
    print('ES check:', e)
PY
fi

echo
echo "Ende: $(date -Iseconds)"
echo "OUT: $OUT"
