#!/usr/bin/env bash
# Diagnose: Matching Skills + MatchResult vs ProjectConsultant
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap
#   bash scripts/diagnose-matching-empty-skills.sh
#   PROJECT_ID=<uuid> bash scripts/diagnose-matching-empty-skills.sh
#
set -euo pipefail

export BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"
PROJECT_ID="${PROJECT_ID:-}"

cd "$BACKEND"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"

"$PYBIN" - <<'PY'
import os, sys
backend = os.environ.get('BACKEND', '/opt/abpe/backend')
if backend not in sys.path:
    sys.path.insert(0, backend)
os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE',
    os.environ.get('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings'),
)

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

    n_pc = ProjectConsultant.objects.filter(project=p).count()
    n_mr = MatchResult.objects.filter(project_request=p).count()
    pcs = (
        ProjectConsultant.objects.filter(project=p)
        .select_related('consultant_cv')
        .order_by('-match_score')[:8]
    )
    mrs = (
        MatchResult.objects.filter(project_request=p)
        .select_related('consultant_cv')
        .order_by('-overall_score')[:8]
    )

    print()
    print(f'--- {p.project_number or p.id} | {p.title[:60]!r}')
    print(f'    id={p.id}')
    print(f'    status={p.status} threshold={p.shortlist_threshold}')
    print(f'    required_skills ({len(names)}): {names[:20]}')
    print(f'    nice_to_have ({len(nice)}): {nice[:10]!r}')
    print(f'    extracted_technologies ({len(tech)}): {tech[:15]!r}')
    print(f'    ProjectConsultants: {n_pc} | MatchResults (Shortlist-UI): {n_mr}')

    for pc in pcs:
        c = getattr(pc, 'consultant_cv', None)
        cname = ''
        aid = ''
        if c is not None:
            cname = (getattr(c, 'full_name', None)
                     or f'{getattr(c, "first_name", "")} {getattr(c, "last_name", "")}'.strip())
            aid = getattr(c, 'aid', '') or ''
        md = getattr(pc, 'match_details', None) or {}
        print(
            f'      PC · score={pc.match_score:.3f} status={pc.status} '
            f'{cname or "?"} {aid} '
            f'matched={md.get("matched_skills")}'
        )

    for r in mrs:
        c = getattr(r, 'consultant_cv', None)
        cname = ''
        aid = ''
        if c is not None:
            cname = (getattr(c, 'full_name', None)
                     or f'{getattr(c, "first_name", "")} {getattr(c, "last_name", "")}'.strip())
            aid = getattr(c, 'aid', '') or ''
        print(
            f'      MR · score={r.overall_score:.3f} rank={r.rank} '
            f'{cname or "?"} {aid} '
            f'matched={r.matched_skills}'
        )

print()
print('======== Engine-Regel (aktuell) ========')
print('  ohne required_skills → Matching bricht ab (keine Blindlinge)')
print('  Shortlist-UI liest MatchResult, nicht ProjectConsultant')
print('  Hinweis: Dieses Script löscht/ändert KEINE DB-Daten.')
PY
