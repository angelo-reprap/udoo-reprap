#!/usr/bin/env bash
# Inspect Stephan Brendel AID profile: folder + education.period lengths from DB/JSON
# Auf ucs5:
#   cd /mnt/public/udoo-reprap && bash scripts/PROBE-brendel-education.sh
set -euo pipefail

ROOT="${AID_PROFILE_ROOT:-/mnt/public/Berater/AID_profile}"
LETTER="${LETTER:-bbb}"
DIR="${DIR:-brendel_stephan}"
PERSON="$ROOT/$LETTER/$DIR"

echo "=== Person-Ordner ==="
if [[ ! -d "$PERSON" ]]; then
  echo "NICHT GEFUNDEN: $PERSON"
  echo "Suche…"
  find "$ROOT" -maxdepth 2 -type d -iname '*brendel*' 2>/dev/null || true
  exit 1
fi
ls -la "$PERSON"
echo
echo "=== PDFs (top-level) ==="
ls -la "$PERSON"/*.pdf 2>/dev/null || echo "(keine)"
echo
echo "=== neu/cv ==="
ls -la "$PERSON/neu/cv/" 2>/dev/null || echo "(kein neu/cv)"

PDF="$(ls -t "$PERSON"/AID-*.pdf 2>/dev/null | head -1 || true)"
if [[ -z "${PDF:-}" ]]; then
  PDF="$(ls -t "$PERSON"/*.pdf 2>/dev/null | head -1 || true)"
fi
echo
echo "=== Quelle PDF: ${PDF:-KEINE} ==="

if [[ -n "${PDF:-}" ]] && command -v pdftotext >/dev/null 2>&1; then
  echo
  echo "=== pdftotext (Ausbildung/Studium-Ausschnitt) ==="
  pdftotext -layout "$PDF" - 2>/dev/null | \
    awk 'BEGIN{IGNORECASE=1}
      /Ausbildung|Studium|Schulung|Zertifikat|Education|Weiterbildung|Berufserfahrung|Projekte/{show=1}
      show{print; n++; if(n>80) exit}'
fi

echo
echo "=== Django: UploadedPDF / Consultant / Education.period ==="
cd /opt/abpe/backend
# shellcheck disable=SC1091
source /opt/abpe/venv311/bin/activate
python3 - <<'PY'
import json, os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from django.db.models import Q
from apps.cv_extractor.models import UploadedPDF, Consultant, Education

q = Q(original_filename__icontains='brendel') | Q(aid__icontains='brendel') | Q(aid__icontains='sb')
ups = list(UploadedPDF.objects.filter(
    Q(original_filename__icontains='brendel') |
    Q(file__icontains='brendel') |
    Q(status__icontains='fail')
).order_by('-id')[:15])
# broader: last failed + name match via related
print(f"UploadedPDF hits (brendel in name/path): {len(ups)}")
for u in ups:
    print(f"  id={u.id} status={u.status} file={getattr(u,'file',None)} orig={getattr(u,'original_filename',None)}")

cons = list(Consultant.objects.filter(
    Q(aid__icontains='brendel') |
    Q(last_name__icontains='brendel') |
    Q(first_name__icontains='Stephan')
).order_by('-id')[:10])
print(f"\nConsultant hits: {len(cons)}")
for c in cons:
    print(f"  id={c.id} aid={c.aid} name={getattr(c,'first_name', '')} {getattr(c,'last_name','')}")

# Prefer consultant with brendel in aid/last_name
c = next((x for x in cons if 'brendel' in (x.aid or '').lower() or 'brendel' in (getattr(x,'last_name','') or '').lower()), None)
if not c and cons:
    c = cons[0]

if c:
    edus = Education.objects.filter(consultant=c)
    print(f"\nEducation rows for consultant id={c.id}: {edus.count()}")
    for e in edus:
        p = e.period or ''
        print(f"  type={e.education_type} period_len={len(p)} period={p!r}")
        print(f"    degree={e.degree!r}")
        print(f"    institution={e.institution!r}")

# Dump extracted_json education.period from latest upload mentioning brendel or recent fail
from apps.cv_extractor.models import UploadedPDF as U
cand = U.objects.filter(
    Q(original_filename__icontains='brendel') |
    Q(file__icontains='brendel')
).order_by('-id').first()
if not cand:
    cand = U.objects.filter(error_message__icontains='varchar').order_by('-id').first()
if cand:
    print(f"\n=== extracted JSON from UploadedPDF id={cand.id} ===")
    for attr in ('extracted_json_export', 'extracted_json', 'pre_json', 'result_json'):
        raw = getattr(cand, attr, None)
        if not raw:
            continue
        data = raw if isinstance(raw, dict) else json.loads(raw)
        edu = data.get('education') or []
        print(f"attr={attr} education_count={len(edu)}")
        for i, e in enumerate(edu):
            if not isinstance(e, dict):
                print(f"  [{i}] {e!r}")
                continue
            p = e.get('period') or ''
            print(f"  [{i}] period_len={len(p)} period={p!r}")
            print(f"       degree={e.get('degree')!r} institution={e.get('institution')!r}")
            print(f"       keys={sorted(e.keys())}")
        break
    else:
        # try consultant.extracted_json_export
        pass

# Consultant extracted export
if c:
    for attr in ('extracted_json_export', 'extracted_json', 'cv_json'):
        raw = getattr(c, attr, None)
        if not raw:
            continue
        data = raw if isinstance(raw, dict) else json.loads(raw)
        edu = data.get('education') or []
        print(f"\n=== consultant.{attr} education ===")
        for i, e in enumerate(edu):
            if not isinstance(e, dict):
                continue
            p = e.get('period') or ''
            print(f"  [{i}] period_len={len(p)} period={p!r}")
            print(f"       degree={(e.get('degree') or e.get('name') or '')!r}")
        break
PY
