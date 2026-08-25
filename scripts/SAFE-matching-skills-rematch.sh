#!/usr/bin/env bash
# Matching mit festen Skills (Default: Java) — zeigt DB vs ES vs ES-only.
#
# Diagnose (schreibt NICHT):
#   MATCH_PROJECT=ANF-2026-0002 MATCH_SKILLS=Java bash scripts/SAFE-matching-skills-rematch.sh
#
# Shortlist überschreiben (Skills am Projekt setzen + MatchResults):
#   WRITE=1 MATCH_PROJECT=ANF-2026-0002 MATCH_SKILLS=Java bash scripts/SAFE-matching-skills-rematch.sh
#
set -euo pipefail
BACKEND="${BACKEND:-/opt/abpe/backend}"
REF="${MATCH_PROJECT:-ANF-2026-0002}"
SKILLS="${MATCH_SKILLS:-Java}"
WRITE="${WRITE:-0}"
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"
export MATCH_PROJECT="$REF"
export MATCH_SKILLS="$SKILLS"
export MATCH_WRITE="$WRITE"

python3 <<'PY'
import os, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
import django
django.setup()

from apps.abpe_matching_workflow.models import ProjectRequest, MatchResult
from apps.abpe_matching_workflow.services.matching_engine import MatchingEngine
from apps.abpe_matching_workflow.services.matching_service import MatchingService

ref = os.environ.get('MATCH_PROJECT', '').strip()
skills_raw = os.environ.get('MATCH_SKILLS', 'Java')
write = os.environ.get('MATCH_WRITE', '0') == '1'
skills = [s.strip() for s in skills_raw.replace(';', ',').split(',') if s.strip()]
skills_payload = [{'name': s, 'weight': 1.0} for s in skills]

p = (
    ProjectRequest.objects.filter(project_number=ref).first()
    or ProjectRequest.objects.filter(id=ref).first()
)
if not p:
    raise SystemExit(f'Projekt nicht gefunden: {ref}')

print('=' * 64)
print(p.project_number, p.title)
print('OVERRIDE skills:', skills)
print('WRITE:', write)
print('=' * 64)

eng = MatchingEngine()
results = eng.run(p, skills_override=skills_payload, min_score=float(p.shortlist_threshold or 0.45))

def _src(r):
    return r.get('match_source') or 'db'

def _srcs(r):
    return list(r.get('match_sources') or [_src(r)])

es_only = [r for r in results if _src(r) == 'es']
es_any = [r for r in results if 'es' in _srcs(r)]
db_only = [r for r in results if _srcs(r) == ['db'] or (len(_srcs(r)) == 1 and _src(r) == 'db')]

print(f'Total ≥ threshold: {len(results)}')
print(f'  db_primary={sum(1 for r in results if _src(r)=="db")}')
print(f'  es_primary={sum(1 for r in results if _src(r)=="es")}  ← nur ES')
print(f'  es_any={len(es_any)}  ← Badge enthält ES')
print(f'  gulp={sum(1 for r in results if _src(r)=="gulp")} flm={sum(1 for r in results if _src(r)=="flm")}')

# Diagnose: ES-Recall roh (auch unter Schwellwert)
orm = eng._stage1_filter(p, eng._expand_with_synonyms(skills, include_related=True))
recall = eng._stage1_es_recall(p, skills, {c.id for c in orm})
print(
    f"\nES-Recall roh: hits={recall.get('hits')} size={recall.get('size_requested')} "
    f"joined={recall.get('joined')} new={len(recall.get('extra') or [])} "
    f"overlap={len(recall.get('overlap_ids') or [])} "
    f"aids={recall.get('aids')} crm_ids={recall.get('crm_ids')}"
)
print('Hinweis: Namazu-Radar (z.B. 538) ≠ Matching-ES-Index (andere Quelle/Limit).')

print('\nES-only (max 15):')
for r in es_only[:15]:
    c = r['consultant_cv']
    print(f"  [ES] {r['overall_score']:.3f} {getattr(c,'full_name',c)} aid={getattr(c,'aid','')}")
if not es_only:
    print('  (keine)')

print('\nTop 12:')
for r in results[:12]:
    c = r['consultant_cv']
    print(
        f"  #{r.get('rank')} {r['overall_score']:.3f} "
        f"{_srcs(r)} {getattr(c,'full_name',c)}"
    )

if not write:
    print('\n(Dry-run — kein Write. WRITE=1 zum Shortlist überschreiben.)')
    raise SystemExit(0)

# Skills am Projekt setzen + MatchResults schreiben
p.required_skills = skills_payload
p.extracted_technologies = skills
p.save(update_fields=['required_skills', 'extracted_technologies'])

MatchResult.objects.filter(project_request=p).delete()
for r in results:
    sd = dict(r.get('skill_details') or {})
    if r.get('match_source'):
        sd.setdefault('match_source', r['match_source'])
    if r.get('match_sources'):
        sd.setdefault('match_sources', r['match_sources'])
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
        calculated_by='matching_engine_skills_override',
    )
    try:
        MatchingService.create_project_consultant(p, r['consultant_cv'], r)
    except Exception as exc:
        print('PC warn:', exc)

p.status = 'matching'
p.save(update_fields=['status'])
print(f'\nOK WRITE: {len(results)} MatchResults, skills={skills}')
print('UI: Ctrl+F5 → Shortlist → Quelle ES')
PY
