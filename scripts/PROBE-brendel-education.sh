#!/usr/bin/env bash
# Inspect Stephan Brendel AID profile: Ordner + education.period aus JSON/DB
# Auf ucs5:
#   cd /mnt/public/udoo-reprap && git pull origin cursor/aid-publish-xml-sanitize-1532
#   bash scripts/PROBE-brendel-education.sh
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
      show{print; n++; if(n>100) exit}'
fi

echo
echo "=== Django: UploadedPDF / Consultant / Education ==="
cd /opt/abpe/backend
# shellcheck disable=SC1091
source /opt/abpe/venv311/bin/activate
python3 - <<'PY'
import json, os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from django.db.models import Q
from apps.cv_extractor.models import UploadedPDF, Consultant, Education

ups = list(UploadedPDF.objects.filter(
    Q(filename__icontains='brendel') |
    Q(consultant_dir__icontains='brendel') |
    Q(last_name__icontains='brendel') |
    Q(file__icontains='brendel')
).order_by('-id')[:15])
print(f"UploadedPDF hits: {len(ups)}")
for u in ups:
    err = (u.error_message or '')[:120].replace('\n', ' ')
    print(f"  id={u.id} status={u.status} dir={u.consultant_dir!r} file={u.filename!r}")
    if err:
        print(f"    err={err}")

cons = list(Consultant.objects.filter(
    Q(aid__icontains='brendel') |
    Q(last_name__icontains='brendel') |
    Q(consultant_dir__icontains='brendel') if hasattr(Consultant, 'consultant_dir') else Q()
).order_by('-id')[:10])
# fallback ohne consultant_dir
if not cons:
    cons = list(Consultant.objects.filter(
        Q(last_name__icontains='brendel') | Q(first_name__icontains='Stephan')
    ).order_by('-id')[:10])

print(f"\nConsultant hits: {len(cons)}")
for c in cons:
    print(f"  id={c.id} aid={c.aid!r} name={c.first_name!r} {c.last_name!r}")

c = next((x for x in cons if 'brendel' in f"{x.aid} {x.last_name}".lower()), None)
if not c and ups and ups[0].consultant_id:
    c = Consultant.objects.filter(id=ups[0].consultant_id).first()
if not c and cons:
    c = cons[0]

if c:
    edus = Education.objects.filter(consultant=c)
    print(f"\nEducation rows consultant id={c.id}: {edus.count()}")
    for e in edus:
        p = e.period or ''
        print(f"  type={e.education_type} period_len={len(p)} period={p!r}")
        print(f"    degree={e.degree!r}")
        print(f"    institution={e.institution!r}")

    raw = getattr(c, 'extracted_json_export', None) or {}
    if isinstance(raw, str):
        raw = json.loads(raw) if raw else {}
    edu = (raw.get('education') or []) if isinstance(raw, dict) else []
    print(f"\n=== consultant.extracted_json_export education ({len(edu)}) ===")
    for i, e in enumerate(edu):
        if not isinstance(e, dict):
            print(f"  [{i}] {e!r}")
            continue
        p = e.get('period') or ''
        print(f"  [{i}] period_len={len(p)} period={p!r}")
        print(f"       degree={(e.get('degree') or e.get('name') or '')!r}")
        print(f"       institution={e.get('institution')!r}")
        print(f"       description={(e.get('description') or '')[:120]!r}")
        print(f"       keys={sorted(e.keys())}")
else:
    print("\nKein Consultant — ggf. Import vor DB-Save abgebrochen.")
    print("Dann nur PDF-Text oben prüfen; period steckt im Pre-JSON der Pipeline.")
PY
