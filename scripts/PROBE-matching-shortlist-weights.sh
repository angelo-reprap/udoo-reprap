#!/usr/bin/env bash
# Probe: Shortlist-Scoring mit ConsultantSkill.weight + optional ES-Recall.
# Schreibt KEINE ProjectConsultant — nur Console-Report.
#
# ucs5:
#   cd /mnt/public/udoo-reprap
#   MATCH_PROJECT=<uuid|project_number> bash scripts/PROBE-matching-shortlist-weights.sh
#   LIMIT=10 MATCH_PROJECT=… bash scripts/PROBE-matching-shortlist-weights.sh
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
LIMIT="${LIMIT:-15}"
REF="${MATCH_PROJECT:-${PROJECT_ID:-}}"

cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"

export MATCH_PROJECT="$REF"
export MATCH_LIMIT="$LIMIT"

python3 <<'PY'
import os, json
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
import django
django.setup()

from apps.abpe_matching_workflow.models import ProjectRequest
from apps.abpe_matching_workflow.services.matching_engine import MatchingEngine

ref = (os.environ.get('MATCH_PROJECT') or '').strip()
limit = int(os.environ.get('MATCH_LIMIT') or 15)
qs = ProjectRequest.objects.all().order_by('-created_at')

if not ref:
    print('Keine MATCH_PROJECT — letzte Anfragen:')
    for row in qs[:15]:
        skills = row.required_skills or []
        n = len(skills) if isinstance(skills, list) else 0
        print(f'  {row.id}  {getattr(row, "project_number", "")}  skills={n}  {getattr(row, "title", "")[:60]}')
    raise SystemExit(0)

import re
import uuid as _uuid

p = None
# UUID-Lookup nur bei gültiger UUID — sonst ValidationError bei project_number
if re.fullmatch(
    r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}',
    ref,
):
    try:
        _uuid.UUID(ref)
        p = ProjectRequest.objects.filter(id=ref).first()
    except (ValueError, TypeError):
        p = None
if p is None:
    p = (
        ProjectRequest.objects.filter(project_number=ref).first()
        or ProjectRequest.objects.filter(project_number__iexact=ref).first()
        or ProjectRequest.objects.filter(title__icontains=ref).first()
    )
if not p:
    print(f'FEHLER: Anfrage nicht gefunden: {ref!r}')
    raise SystemExit(1)

eng = MatchingEngine()
print('=' * 64)
print(f'Projekt: {getattr(p, "project_number", p.id)}  {p.title}')
print(f'required_skills: {eng._skill_names(p.required_skills)}')
print(f'extracted_technologies: {list(p.extracted_technologies or [])}')
print(f'threshold: {p.shortlist_threshold}')
print(f'scoring blends: coverage={eng.cov_blend} strength={eng.str_blend}')
print(f'es_recall: {json.dumps(eng.es_recall_cfg or {"enabled": "(default on)"}, ensure_ascii=False)}')
print('=' * 64)

results = eng.run(p, limit=limit, min_score=0.0)
above = [r for r in results if r['overall_score'] >= float(p.shortlist_threshold or 0.5)]
print(f'Top {len(results)} (min_score=0 diagnostisch); ≥ threshold: {len(above)}\n')
# Coverage-Histogramm
from collections import Counter
cov_bucket = Counter()
for r in results:
    c = (r.get('skill_details') or {}).get('coverage') or 0
    cov_bucket[round(float(c), 1)] += 1
print('coverage_hist:', dict(sorted(cov_bucket.items())))
print()
for r in results:
    c = r['consultant_cv']
    sd = r.get('skill_details') or {}
    name = getattr(c, 'full_name', None) or f'{c.first_name} {c.last_name}'
    mark = '✓' if r['overall_score'] >= float(p.shortlist_threshold or 0.5) else '·'
    print(
        f"{mark}#{r.get('rank')}  score={r['overall_score']:.3f}  "
        f"skill={r['skill_score']:.3f} "
        f"(cov={sd.get('coverage')} eff={sd.get('coverage_eff')} "
        f"str={sd.get('strength')} q={sd.get('quality')})  "
        f"{name}  aid={getattr(c, 'aid', '')}"
    )
    mw = sd.get('matched_weights') or []
    if mw:
        tops = ', '.join(
            f"{m['skill']}→{m.get('matched_as')}@{m.get('consultant_weight')}"
            for m in mw[:6]
        )
        print(f"     matched: {tops}")
    miss = sd.get('missing_required') or []
    if miss:
        print(f"     missing: {miss[:8]}")

out = Path(os.environ.get('OUT') or '/tmp/matching-shortlist-weights-probe.json')
payload = {
    'project_id': str(p.id),
    'project_number': getattr(p, 'project_number', ''),
    'count': len(results),
    'results': [
        {
            'rank': r.get('rank'),
            'overall_score': r['overall_score'],
            'skill_score': r['skill_score'],
            'skill_details': r.get('skill_details'),
            'aid': getattr(r['consultant_cv'], 'aid', ''),
            'name': getattr(r['consultant_cv'], 'full_name', '')
                or f"{r['consultant_cv'].first_name} {r['consultant_cv'].last_name}",
            'matched_skills': r.get('matched_skills'),
            'missing_skills': r.get('missing_skills'),
        }
        for r in results
    ],
}
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'\nJSON → {out}')
PY
