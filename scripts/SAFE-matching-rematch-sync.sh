#!/usr/bin/env bash
# Sync-Rematch: MatchingEngine laufen lassen und MatchResults schreiben (ohne Celery).
# Nutzt wenn Shortlist nach Reset leer ist.
#
#   MATCH_PROJECT=ANF-2026-0002 bash scripts/SAFE-matching-rematch-sync.sh
#
set -euo pipefail
BACKEND="${BACKEND:-/opt/abpe/backend}"
REF="${MATCH_PROJECT:-ANF-2026-0002}"
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"
export MATCH_PROJECT="$REF"

python3 <<'PY'
import os, traceback
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
import django
django.setup()

from apps.abpe_matching_workflow.models import ProjectRequest, MatchResult, ProjectConsultant
from apps.abpe_matching_workflow.services.matching_engine import MatchingEngine
from apps.abpe_matching_workflow.services.matching_service import MatchingService

ref = os.environ.get('MATCH_PROJECT', '').strip()
p = (
    ProjectRequest.objects.filter(project_number=ref).first()
    or ProjectRequest.objects.filter(id=ref).first()
)
if not p:
    raise SystemExit(f'Projekt nicht gefunden: {ref}')

print('=' * 64)
print(p.project_number, p.title)
print('skills:', p.required_skills)
print('threshold:', p.shortlist_threshold)
print('MatchResults before:', MatchResult.objects.filter(project_request=p).count())
print('=' * 64)

try:
    results = MatchingEngine().run(p)
except Exception:
    traceback.print_exc()
    raise SystemExit(2)

print(f'Engine results: {len(results)}')
for r in results[:8]:
    c = r['consultant_cv']
    sd = r.get('skill_details') or {}
    print(
        f"  #{r.get('rank')} {r['overall_score']:.3f} "
        f"str={sd.get('strength')} [{r.get('match_source')}] "
        f"{getattr(c,'full_name',c)}"
    )

# Atomar ersetzen nur wenn Treffer da
if not results:
    print('WARN: 0 Treffer — bestehende MatchResults werden NICHT gelöscht')
    raise SystemExit(3)

MatchResult.objects.filter(project_request=p).delete()
n = 0
for r in results:
    sd = dict(r.get('skill_details') or {})
    if r.get('match_source'):
        sd.setdefault('match_source', r['match_source'])
    if r.get('match_sources'):
        sd.setdefault('match_sources', r['match_sources'])
    if r.get('rank_score') is not None:
        sd['rank_score'] = r['rank_score']
    MatchResult.objects.create(
        project_request=p,
        consultant_cv=r['consultant_cv'],
        overall_score=r['overall_score'],
        skill_score=r['skill_score'],
        industry_score=r['industry_score'],
        experience_score=r['experience_score'],
        location_score=r['location_score'],
        rank=r['rank'],
        matched_skills=r['matched_skills'],
        missing_skills=r['missing_skills'],
        skill_details=sd,
        calculated_by='matching_engine_sync',
    )
    try:
        MatchingService.create_project_consultant(p, r['consultant_cv'], r)
    except Exception as exc:
        print('PC sync warn:', exc)
    n += 1

p.status = 'matching'
p.save(update_fields=['status'])
print(f'OK geschrieben: {n} MatchResults')
print('MatchResults after:', MatchResult.objects.filter(project_request=p).count())
print('ProjectConsultants:', ProjectConsultant.objects.filter(project=p).count())
er = p.extracted_requirements if isinstance(p.extracted_requirements, dict) else {}
print('backoffice:', len(er.get('_matching_backoffice') or []))
print('external_stats:', er.get('_matching_external_stats'))
PY
