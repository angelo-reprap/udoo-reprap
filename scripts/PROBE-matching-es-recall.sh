#!/usr/bin/env bash
# Diagnose: ES-Recall für Matching (Pipeline vs Index).
#
#   MATCH_PROJECT=ANF-2026-0002 bash scripts/PROBE-matching-es-recall.sh
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
import os, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
import django
django.setup()

from apps.abpe_matching_workflow.models import ProjectRequest
from apps.abpe_matching_workflow.services.matching_engine import MatchingEngine, _es_hosts, _cfg

ref = os.environ.get('MATCH_PROJECT', '').strip()
p = (
    ProjectRequest.objects.filter(project_number=ref).first()
    or ProjectRequest.objects.filter(id=ref).first()
)
if not p:
    raise SystemExit(f'Projekt nicht gefunden: {ref}')

eng = MatchingEngine()
skills = eng._skill_names(p.required_skills)
skills += list(p.extracted_technologies or [])
skills = list(dict.fromkeys(skills))
cfg = eng.es_recall_cfg or {}
index = cfg.get('index') or 'abpe_matching_profiles_probe'

print('=' * 64)
print(p.project_number, p.title)
print('skills:', skills)
print('es_recall cfg:', json.dumps(cfg or {'enabled': '(default on)'}, ensure_ascii=False))
print('es hosts:', _es_hosts())
print('index:', index)
print('=' * 64)

# 1) Stage1 ORM
req_exp = eng._expand_with_synonyms(skills, include_related=True)
orm = eng._stage1_filter(p, req_exp)
orm_ids = {c.id for c in orm}
print(f'Stage1 ORM: {len(orm)} Kandidaten')

# 2) ES raw
recall = eng._stage1_es_recall(p, skills, orm_ids)
print(
    f"ES-Recall: hits={recall.get('hits')} joined={recall.get('joined')} "
    f"new={len(recall.get('extra') or [])} overlap={len(recall.get('overlap_ids') or [])} "
    f"skip={recall.get('skip') or '-'}"
)

# ES ping/count if possible
try:
    from elasticsearch import Elasticsearch
    es = Elasticsearch(_es_hosts(), verify_certs=False, request_timeout=20)
    print('ES ping:', es.ping())
    if es.indices.exists(index=index):
        print('ES count:', es.count(index=index).get('count'))
        # sample skill_names for python
        q = {'term': {'skill_names': 'python'}}
        n = es.count(index=index, query=q).get('count')
        print('docs skill_names=python:', n)
    else:
        print('Index fehlt:', index)
except Exception as e:
    print('ES diagnose error:', e)

print('\nNeu nur über ES (max 10):')
for c in (recall.get('extra') or [])[:10]:
    print(f"  [ES] {getattr(c,'full_name',c)} aid={getattr(c,'aid','')}")

print('\nOverlap ORM∩ES (max 10) — Badge wird db+es:')
overlap = recall.get('overlap_ids') or set()
by_id = {c.id: c for c in orm}
for i, cid in enumerate(list(overlap)[:10]):
    c = by_id.get(cid)
    if c:
        print(f"  [DB+ES] {getattr(c,'full_name',c)} aid={getattr(c,'aid','')}")

print('\nHinweis: es_primary=0 ist OK wenn ES niemanden NEU findet.')
print('es_any / Dropdown ES > 0 nach Rematch = Index hat mitgetroffen.')
PY
