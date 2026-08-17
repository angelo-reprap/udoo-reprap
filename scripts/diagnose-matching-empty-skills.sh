#!/usr/bin/env bash
# Diagnose: Matching ohne / mit leeren required_skills
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap
#   bash scripts/diagnose-matching-empty-skills.sh
#   PROJECT_ID=<uuid> bash scripts/diagnose-matching-empty-skills.sh
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"
PROJECT_ID="${PROJECT_ID:-}"

cd "$BACKEND"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"

"$PYBIN" - <<'PY'
import os, json
import django
django.setup()

from apps.abpe_matching_workflow.models import ProjectRequest, ProjectConsultant, MatchResult

pid = os.environ.get('PROJECT_ID', '').strip()

print('======== Matching Empty-Skills Diagnose ========')
qs = ProjectRequest.objects.filter(is_archived=False).order_by('-updated_at', '-created_at')
if pid:
    qs = ProjectRequest.objects.filter(id=pid)

rows = list(qs[:15])
if not rows:
    print('Keine ProjectRequest gefunden.')
    raise SystemExit(1)

for p in rows:
    skills = p.required_skills or []
    nice = p.nice_to_have_skills or []
    tech = list(getattr(p, 'extracted_technologies', None) or [])
    names = []
    for s in skills:
        if isinstance(s, dict) and s.get('name'):
            names.append(s['name'])
        elif isinstance(s, str) and s.strip():
            names.append(s.strip())
    pcs = ProjectConsultant.objects.filter(project=p).order_by('-match_score')[:8]
    print()
    print(f'--- {p.project_number or p.id} | {p.title[:60]!r}')
    print(f'    id={p.id}')
    print(f'    status={p.status} threshold={p.shortlist_threshold}')
    print(f'    required_skills ({len(names)}): {names[:20]}')
    print(f'    nice_to_have ({len(nice)}): {nice[:10]!r}')
    print(f'    extracted_technologies ({len(tech)}): {tech[:15]!r}')
    print(f'    ProjectConsultants: {ProjectConsultant.objects.filter(project=p).count()}')
    for pc in pcs:
        c = getattr(pc, 'consultant', None)
        cname = ''
        if c:
            cname = f'{getattr(c,"first_name","")} {getattr(c,"last_name","")}'.strip()
        # match_details may hold display skills
        md = getattr(pc, 'match_details', None) or {}
        print(
            f'      · score={pc.match_score:.3f} status={pc.status} '
            f'{cname or pc.consultant_id} '
            f'matched={getattr(pc,"matched_skills", None) or md.get("matched_skills")} '
            f'missing={getattr(pc,"missing_skills", None) or md.get("missing_skills")}'
        )

# Engine behaviour when skills empty
print()
print('======== Engine-Regel bei leeren Skills ========')
print('matching_engine._stage2_score:')
print('  if required_original is empty → req_score = 1.0  (!)')
print('  → overall ≈ 0.50*1.0 + industry + exp + loc  → Blindlinge ~45–70%')
print('Fix-Richtung: req_score=0.0 wenn keine required_skills; Matching ablehnen/warnen.')
PY
